import sys, json, time, csv, urllib.request, urllib.parse, datetime as dt

out = sys.argv[1]
LAT, LON = 50.43, -5.13
START, END = dt.date(2016, 10, 1), dt.date.today() - dt.timedelta(days=1)
MARINE = ["wave_height", "wave_period", "wave_direction", "swell_wave_height", "swell_wave_period",
          "swell_wave_peak_period", "swell_wave_direction", "wind_wave_height", "sea_level_height_msl"]
WIND = ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]


def get(base, hourly, s, e):
    q = dict(latitude=LAT, longitude=LON, hourly=",".join(hourly), start_date=s.isoformat(),
             end_date=e.isoformat(), timezone="UTC")
    url = base + "?" + urllib.parse.urlencode(q)
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as ex:
            err = ex
            if hasattr(ex, "read"):
                print("HTTP error body:", ex.read()[:500], file=sys.stderr)
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"{base} {s}..{e}: {err}")


data = {}
meta = {}
s = START
while s <= END:
    e = min(dt.date(s.year, 12, 31), END)
    for base, hv in (("https://marine-api.open-meteo.com/v1/marine", MARINE),
                     ("https://archive-api.open-meteo.com/v1/archive", WIND)):
        j = get(base, hv, s, e)
        meta[base] = {k: j.get(k) for k in ("latitude", "longitude", "hourly_units")}
        for i, t in enumerate(j["hourly"]["time"]):
            row = data.setdefault(t, {})
            for v in hv:
                row[v] = j["hourly"][v][i]
    print(s, e, len(data), flush=True)
    s = e + dt.timedelta(days=1)
    time.sleep(1)

cols = ["time"] + MARINE + WIND
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for t in sorted(data):
        w.writerow([t] + [data[t].get(c) if data[t].get(c) is not None else "" for c in cols[1:]])
print(json.dumps(meta, indent=1))
ts = sorted(data)
print("rows", len(ts), "from", ts[0], "to", ts[-1])
for c in MARINE + WIND:
    vals = [data[t].get(c) for t in ts]
    nn = [i for i, v in enumerate(vals) if v is not None]
    print(f"{c}: null {100 * (len(ts) - len(nn)) / len(ts):.1f}%  first {ts[nn[0]] if nn else None}  last {ts[nn[-1]] if nn else None}")
