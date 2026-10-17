import sys, json, csv
import numpy as np
import rasterio
from rasterio.transform import xy

tif, outdir = sys.argv[1], sys.argv[2]
poly = [(-5.1024, 50.4165), (-5.1004, 50.4196), (-5.1381, 50.4373), (-5.1487, 50.4206)]


def inside(x, y, p):
    n, c = len(p), False
    for i in range(n):
        x1, y1 = p[i]; x2, y2 = p[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


with rasterio.open(tif) as ds:
    print("crs", ds.crs, "shape", ds.shape, "bounds", ds.bounds, "nodata", ds.nodata, "dtype", ds.dtypes)
    a = ds.read(1)
    rows = []
    for r in range(ds.height):
        for c in range(ds.width):
            lon, lat = xy(ds.transform, r, c)
            v = a[r, c]
            if ds.nodata is not None and v == ds.nodata:
                continue
            if not np.isfinite(v):
                continue
            if inside(lon, lat, poly):
                rows.append((round(lon, 6), round(lat, 6), float(v)))

with open(f"{outdir}/emodnet_north_fistral_clipped.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["lon", "lat", "depth_m"]); w.writerows(rows)

gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "North Fistral"},
      "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in poly] + [list(poly[0])]]}}]}
with open(f"{outdir}/north_fistral_area.geojson", "w") as f:
    json.dump(gj, f, indent=2)

d = np.array([r[2] for r in rows])
print("cells", len(rows), "min", d.min() if len(d) else None, "max", d.max() if len(d) else None)
for r in rows[:5]: print(r)
