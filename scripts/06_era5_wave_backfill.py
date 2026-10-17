import sys, json, time, csv, urllib.request, urllib.parse, datetime as dt
import numpy as np

out, main = sys.argv[1], sys.argv[2]
V = ["wave_height", "wave_period", "wave_direction"]
START, END = dt.date(2016, 10, 1), dt.date.today() - dt.timedelta(days=1)
data, s = {}, START
while s <= END:
    e = min(dt.date(s.year, 12, 31), END)
    q = dict(latitude=50.43, longitude=-5.13, hourly=",".join(V), start_date=s.isoformat(), end_date=e.isoformat(),
             timezone="UTC", models="era5_ocean")
    for i in range(4):
        try:
            with urllib.request.urlopen("https://marine-api.open-meteo.com/v1/marine?" + urllib.parse.urlencode(q), timeout=120) as r:
                j = json.load(r); break
        except Exception as ex:
            err = ex; time.sleep(2 ** (i + 1))
    else:
        raise RuntimeError(err)
    grid = (j["latitude"], j["longitude"])
    for i, t in enumerate(j["hourly"]["time"]):
        data[t] = [j["hourly"][v][i] for v in V]
    print(s, e, len(data), flush=True); s = e + dt.timedelta(days=1); time.sleep(1)

ts = sorted(data)
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["time"] + V)
    for t in ts: w.writerow([t] + ["" if x is None else x for x in data[t]])
print("grid", grid, "rows", len(ts), ts[0], ts[-1])
for k, v in enumerate(V):
    nn = [t for t in ts if data[t][k] is not None]
    print(f"{v}: null {100 * (len(ts) - len(nn)) / len(ts):.2f}%  first {nn[0] if nn else None} last {nn[-1] if nn else None}")

m = {r["time"]: r for r in csv.DictReader(open(main))}
for k, v in enumerate(V):
    a, b = [], []
    for t in ts:
        x = data[t][k]; y = m.get(t, {}).get(v, "")
        if x is not None and y != "":
            a.append(float(x)); b.append(float(y))
    a, b = np.array(a), np.array(b)
    if v == "wave_direction":
        d = (a - b + 180) % 360 - 180
        ra, rb = np.radians(a), np.radians(b)
        # circular correlation (Jammalamadaka)
        ma = np.arctan2(np.sin(ra).mean(), np.cos(ra).mean()); mb = np.arctan2(np.sin(rb).mean(), np.cos(rb).mean())
        sa, sb = np.sin(ra - ma), np.sin(rb - mb)
        r = (sa * sb).sum() / np.sqrt((sa ** 2).sum() * (sb ** 2).sum())
        print(f"{v}: n={len(a)} mean diff (ERA5-main) {d.mean():.1f} deg, mean abs diff {np.abs(d).mean():.1f} deg, circular r {r:.3f}")
    else:
        print(f"{v}: n={len(a)} mean ERA5 {a.mean():.2f} main {b.mean():.2f} mean diff {(a - b).mean():+.2f}, MAE {np.abs(a - b).mean():.2f}, r {np.corrcoef(a, b)[0, 1]:.3f}")
