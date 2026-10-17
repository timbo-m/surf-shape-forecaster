"""Sort CCO survey files by date/type, clip to North Fistral polygon, write index."""
import sys, os, re, csv, json, shutil
from collections import defaultdict
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPoint, mapping
from shapely.ops import transform as shp_transform

src, out, geojson = sys.argv[1], sys.argv[2], sys.argv[3]
TOPO_CUTOFF = "20161014"  # last 10 years

to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
to_ll = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
ring = json.load(open(geojson))["features"][0]["geometry"]["coordinates"][0]
poly = Polygon([to_bng.transform(x, y) for x, y in ring])
P_AREA = poly.area
minx, miny, maxx, maxy = poly.bounds

def inside(e, n):
    from shapely import contains_xy
    return contains_xy(poly, e, n)

groups = defaultdict(list)  # (date, type) -> files
problems = []
pat = re.compile(r"_(\d{8})([a-z]+)(?:\.clash\d+)?\.(txt|asc|tif)$")
for sub, kind in (("topographic", "topo"), ("hydrographic", "bathy"), ("lidar", "lidar")):
    d = os.path.join(src, sub)
    for f in sorted(os.listdir(d)):
        m = pat.search(f)
        if not m:
            problems.append(f"{sub}/{f}: name not recognised"); continue
        date, code = m.group(1), m.group(2)
        if kind == "topo":
            t = f"topo-{code}"
        elif kind == "lidar":
            t = "lidar-dtm" if code.endswith("f") else "lidar-dsm"
        else:
            t = "bathy"
        groups[(date, t)].append(os.path.join(d, f))

rows = []
for (date, t), files in sorted(groups.items()):
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    E, N, Z = [], [], []
    total = 0
    for f in files:
        try:
            if f.endswith(".txt"):
                with open(f, newline="") as fh:
                    r = csv.reader(fh, delimiter="\t")
                    hdr = [h.strip() for h in next(r)]
                    ie, inn, iz = hdr.index("Easting"), hdr.index("Northing"), hdr.index("Elevation_OD" if "Elevation_OD" in hdr else "Elevation")
                    a = np.array([[float(x[ie]), float(x[inn]), float(x[iz])] for x in r if len(x) > iz and x[iz].strip()])
                if len(a) == 0: continue
                total += len(a)
                k = inside(a[:, 0], a[:, 1])
                E.append(a[k, 0]); N.append(a[k, 1]); Z.append(a[k, 2])
            else:
                with rasterio.open(f) as ds:
                    if ds.crs is not None and ds.crs.to_epsg() != 27700:
                        problems.append(f"{os.path.basename(f)}: CRS {ds.crs}, skipped"); continue
                    b = ds.bounds
                    if b.right < minx or b.left > maxx or b.top < miny or b.bottom > maxy:
                        continue
                    arr = ds.read(1, masked=True)
                    m = ~geometry_mask([mapping(poly)], out_shape=arr.shape, transform=ds.transform)
                    total += int((~np.ma.getmaskarray(arr)).sum())
                    m &= ~np.ma.getmaskarray(arr)
                    rr, cc = np.nonzero(m)
                    xs, ys = rasterio.transform.xy(ds.transform, rr, cc)
                    E.append(np.asarray(xs)); N.append(np.asarray(ys)); Z.append(arr.data[rr, cc].astype(float))
        except Exception as ex:
            problems.append(f"{os.path.basename(f)}: {type(ex).__name__}: {ex}")
    e = np.concatenate(E) if E else np.array([]); n = np.concatenate(N) if N else np.array([]); z = np.concatenate(Z) if Z else np.array([])
    if len(e) and t.startswith("lidar"):  # tiles can overlap; keep one value per cell
        _, idx = np.unique(np.round(np.c_[e, n], 2), axis=0, return_index=True)
        e, n, z = e[idx], n[idx], z[idx]
    folder = os.path.join(out, f"{iso}_{t}")
    os.makedirs(folder, exist_ok=True)
    os.makedirs(os.path.join(folder, "original"), exist_ok=True)
    for f in files:
        shutil.copy2(f, os.path.join(folder, "original"))
    csvp = os.path.join(folder, f"{iso}_{t}_clipped.csv")
    lon, lat = to_ll.transform(e, n) if len(e) else (np.array([]), np.array([]))
    with open(csvp, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["easting", "northing", "lon", "lat", "z_odn"])
        for row in zip(np.round(e, 3), np.round(n, 3), np.round(lon, 7), np.round(lat, 7), np.round(z, 3)):
            w.writerow(row)
    if len(e) >= 3:
        hull = MultiPoint(np.c_[e, n]).convex_hull.intersection(poly)
        cov_hull = hull.area / P_AREA
    else:
        cov_hull = 0.0
    cov_cells = (len(e) / P_AREA) if t.startswith("lidar") else None  # 1 m cells -> m^2
    rows.append(dict(date=iso, type=t, in_last_10y=date >= TOPO_CUTOFF, n_source_files=len(files),
                     source_files=";".join(os.path.basename(f) for f in files),
                     points_total=total, points_inside=len(e), z_min=round(float(z.min()), 3) if len(z) else "",
                     z_max=round(float(z.max()), 3) if len(z) else "",
                     coverage_hull_pct=round(100 * cov_hull, 2),
                     coverage_cells_pct=round(100 * cov_cells, 2) if cov_cells is not None else "",
                     clipped_csv=os.path.relpath(csvp, out)))
    print(iso, t, len(files), len(e), rows[-1]["z_min"], rows[-1]["z_max"], rows[-1]["coverage_hull_pct"], rows[-1]["coverage_cells_pct"], flush=True)

with open(os.path.join(out, "index.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("polygon area m2", round(P_AREA))
print("PROBLEMS", len(problems)); [print(" ", p) for p in problems]
