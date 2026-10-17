"""v3: whole-Fistral area (Little / North / South Fistral + offshore), re-clip all surveys + EMODnet, zone column."""
import sys, os, re, csv, json, shutil
from collections import defaultdict
import numpy as np, rasterio
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPoint, mapping, box
from shapely import contains_xy

B = r"C:\Users\thoma\Surf Forecast\fistral\data\bathymetry"
SRC = B + r"\surveys\raw\extracted\cco_data-20261014090801-927d\data"
OUT = B + r"\surveys"
fw = Transformer.from_crs(4326, 27700, always_xy=True); bw = Transformer.from_crs(27700, 4326, always_xy=True)

# ---- polygon (BNG) ----
# back-of-beach line, south -> north, traced from CCO topo + lidar (easternmost +3..+7 m beach points, ~30 m landward)
SHORE = [(179560, 61540), (179830, 61650), (179930, 61800), (179990, 61950), (180060, 62250),
         (180120, 62450), (180200, 62650), (180170, 62850), (180100, 63000)]
N_OFF = (177258.8, 64424.1)   # unchanged from v1/v2
S_OFF = (176000.0, 61700.0)   # out past Pentire Point East (tip ~177925, 61640 from EMODnet land cells)
corners = SHORE + [N_OFF, S_OFF]
poly = Polygon(corners)
assert poly.is_valid
ll = [tuple(round(v, 6) for v in bw.transform(*p)) for p in corners]
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {
    "name": "Fistral v3 (Little, North, South Fistral + offshore)",
    "note": "Shore edge follows the back of the beach (from CCO surveys/lidar) from the foot of Pentire headland to the foot of Towan Head; offshore edge fans across the bay mouth (Towan Head - Pentire Point East) to ~3 km WNW. Zones: little = north of the main beach's north end (OSM), north/south split at mid-beach, offshore = >700 m seaward of the back-of-beach line."},
    "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ll] + [list(ll[0])]]}}]},
    open(B + r"\fistral_area_v3.geojson", "w"), indent=2)

from shapely.geometry import LineString
from shapely import distance as shp_distance, points as shp_points
shore_line = LineString(SHORE)
BEACH_S, BEACH_N = fw.transform(-5.1072678, 50.4134029), fw.transform(-5.0997205, 50.4220505)  # OSM beach ends
N_LITTLE = BEACH_N[1]                      # north of main beach's north end = Little Fistral
N_MID = (BEACH_S[1] + BEACH_N[1]) / 2      # North / South Fistral split at mid-beach
OFFSHORE_M = 700

def zones(e, n):
    d = shp_distance(shore_line, shp_points(np.c_[e, n]))
    z = np.where(n >= N_LITTLE, "little", np.where(n >= N_MID, "north", "south")).astype(object)
    z[d > OFFSHORE_M] = "offshore"
    return z

near = shore_line.buffer(OFFSHORE_M).intersection(poly)
big = 1e7
ZP = {"little": near.intersection(box(-big, N_LITTLE, big, big)),
      "north": near.intersection(box(-big, N_MID, big, N_LITTLE)),
      "south": near.intersection(box(-big, -big, big, N_MID)),
      "offshore": poly.difference(near)}
print("corners lonlat", ll, "area km2", round(poly.area / 1e6, 3), {z: round(p.area / 1e6, 3) for z, p in ZP.items()})
# ---- group survey files (same rules as v1/v2) ----
groups = defaultdict(list)
pat = re.compile(r"_(\d{8})([a-z]+)(?:\.clash\d+)?\.(txt|asc|tif)$")
for sub, kind in (("topographic", "topo"), ("hydrographic", "bathy"), ("lidar", "lidar")):
    for f in sorted(os.listdir(os.path.join(SRC, sub))):
        m = pat.search(f)
        if not m: continue
        date, code = m.group(1), m.group(2)
        t = f"topo-{code}" if kind == "topo" else ("lidar-dtm" if code.endswith("f") else "lidar-dsm") if kind == "lidar" else "bathy"
        groups[(date, t)].append(os.path.join(SRC, sub, f))

def read_points(files, lidar):
    E, N, Z = [], [], []
    for f in files:
        if f.endswith(".txt"):
            r = csv.reader(open(f, newline=""), delimiter="\t"); hdr = [h.strip() for h in next(r)]
            ie, inn, iz = hdr.index("Easting"), hdr.index("Northing"), hdr.index("Elevation_OD" if "Elevation_OD" in hdr else "Elevation")
            a = np.array([[float(x[ie]), float(x[inn]), float(x[iz])] for x in r if len(x) > iz and x[iz].strip()])
            if len(a) == 0: continue
            k = contains_xy(poly, a[:, 0], a[:, 1]); E.append(a[k, 0]); N.append(a[k, 1]); Z.append(a[k, 2])
        else:
            with rasterio.open(f) as ds:
                b = ds.bounds
                if not box(b.left, b.bottom, b.right, b.top).intersects(poly): continue
                arr = ds.read(1, masked=True)
                m = ~geometry_mask([mapping(poly)], out_shape=arr.shape, transform=ds.transform) & ~np.ma.getmaskarray(arr)
                rr, cc = np.nonzero(m); xs, ys = rasterio.transform.xy(ds.transform, rr, cc)
                E.append(np.asarray(xs)); N.append(np.asarray(ys)); Z.append(arr.data[rr, cc].astype(float))
    e = np.concatenate(E) if E else np.array([]); n = np.concatenate(N) if N else np.array([]); z = np.concatenate(Z) if Z else np.array([])
    if lidar and len(e):
        _, idx = np.unique(np.round(np.c_[e, n], 2), axis=0, return_index=True); e, n, z = e[idx], n[idx], z[idx]
    return e, n, z

def write(path, e, n, z, zone):
    lon, lat = bw.transform(e, n) if len(e) else (np.array([]), np.array([]))
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["easting", "northing", "lon", "lat", "z_odn", "zone"])
        for row in zip(np.round(e, 3), np.round(n, 3), np.round(lon, 7), np.round(lat, 7), np.round(z, 3), zone): w.writerow(row)

def stats(e, n, z, zone, lidar):
    out = dict(points_inside_v3=len(e), z_min_v3=round(float(z.min()), 3) if len(z) else "", z_max_v3=round(float(z.max()), 3) if len(z) else "")
    for zn, zp in ZP.items():
        k = zone == zn
        out[f"pts_{zn}_v3"] = int(k.sum())
        if lidar: cov = k.sum() / zp.area
        elif k.sum() >= 3: cov = MultiPoint(np.c_[e[k], n[k]]).convex_hull.intersection(zp).area / zp.area
        else: cov = 0
        out[f"cov_{zn}_pct_v3"] = round(100 * cov, 2)
    return out

res = {}
for (date, t), files in sorted(groups.items()):
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    lidar = t.startswith("lidar")
    e, n, z = read_points(files, lidar)
    zone = zones(e, n) if len(e) else np.array([], dtype=object)
    folder = os.path.join(OUT, f"{iso}_{t}"); os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, f"{iso}_{t}_clipped_v3.csv"); write(p, e, n, z, zone)
    st = stats(e, n, z, zone, lidar); st["clipped_csv_v3"] = os.path.relpath(p, OUT); res[(iso, t)] = st
    print(iso, t, st["points_inside_v3"], st["z_min_v3"], st["z_max_v3"], {k: v for k, v in st.items() if k.startswith(("pts_", "cov_"))}, flush=True)

# EMODnet (wider v3 download)
with rasterio.open(B + r"\emodnet_fistral_v3.tif") as ds:
    a = ds.read(1); r, c = np.indices(a.shape); xs, ys = rasterio.transform.xy(ds.transform, r.ravel(), c.ravel())
X, Y = fw.transform(np.array(xs), np.array(ys)); Zv = a.ravel().astype(float)
k = contains_xy(poly, X, Y) & np.isfinite(Zv)
ze = zones(X[k], Y[k]); write(B + r"\emodnet_fistral_clipped_v3.csv", X[k], Y[k], Zv[k], ze)
print("EMODnet v3 cells", int(k.sum()), "z", Zv[k].min(), Zv[k].max(), {zn: int((ze == zn).sum()) for zn in ZP})

# index
idx = OUT + r"\index.csv"; shutil.copy2(idx, OUT + r"\index_v2_backup.csv")
rows = list(csv.DictReader(open(idx)))
for r_ in rows: r_.update(res[(r_["date"], r_["type"])])
with open(idx, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("index rows", len(rows))
