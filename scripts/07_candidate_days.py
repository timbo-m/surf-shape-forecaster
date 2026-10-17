"""Heuristic shortlist of likely barrel days at North Fistral from hourly conditions."""
import sys
import numpy as np
import pandas as pd

cond, era5, out = sys.argv[1:4]
m = pd.read_csv(cond, parse_dates=["time"])
e = pd.read_csv(era5, parse_dates=["time"])
SPLIT = pd.Timestamp("2021-10-01 03:00")

# main model: swell partition; peak period where present, else swell mean period
main = pd.DataFrame({"time": m.time,
                     "h": m.swell_wave_height,
                     "t": m.swell_wave_peak_period.fillna(m.swell_wave_period),
                     "t_kind": np.where(m.swell_wave_peak_period.notna(), "swell_peak", "swell_mean"),
                     "d": m.swell_wave_direction})
# ERA5: total sea only, offsets measured vs main total waves over the overlap
er = pd.DataFrame({"time": e.time, "h": e.wave_height + 0.18, "t": e.wave_period + 0.66,
                   "t_kind": "era5_total_mean+0.66", "d": e.wave_direction})
df = pd.concat([er[er.time < SPLIT].assign(source="era5"), main[main.time >= SPLIT].assign(source="open-meteo")])
df = df.merge(m[["time", "wind_speed_10m", "wind_direction_10m"]], on="time", how="left")
df["local"] = df.time.dt.tz_localize("UTC").dt.tz_convert("Europe/London")
df = df[(df.local.dt.hour >= 6) & (df.local.dt.hour <= 18)].copy()
df["date"] = df.local.dt.date

ws, wd = df.wind_speed_10m, df.wind_direction_10m
df["ok"] = (df.h.between(1.0, 3.0) & (df.t >= 10) & df.d.between(250, 310)
            & (wd.between(60, 160) | (ws < 10)) & (ws <= 30))
offshore = np.cos(np.radians(wd - 110))  # 110 deg = straight offshore for a ~290 deg facing beach
df["s_period"] = ((df.t - 10) / 6).clip(0, 1)
s_speed = np.interp(ws, [0, 5, 20, 30], [0.7, 1.0, 1.0, 0.4])
df["s_wind"] = s_speed * np.where(ws < 10, np.maximum(0.7, offshore.clip(0, 1)), offshore.clip(0, 1))
df["s_size"] = (1 - (df.h - 1.8).abs() / 1.2).clip(0, 1)
df["score"] = 0.4 * df.s_period + 0.3 * df.s_wind + 0.3 * df.s_size

rows = []
for date, g in df.sort_values("time").groupby("date"):
    g = g.reset_index(drop=True)
    best = None
    for i in range(len(g) - 2):
        w = g.iloc[i:i + 3]
        if w.ok.all() and (w.time.diff().dropna() == pd.Timedelta("1h")).all():
            s = w.score.mean()
            if best is None or s > best[0]:
                best = (s, w)
    if best:
        s, w = best
        rows.append(dict(date=date, window_local=f"{w.local.iloc[0]:%H:%M}-{w.local.iloc[-1]:%H:%M}",
                         swell_height_m=round(w.h.mean(), 2), period_s=round(w.t.mean(), 1), period_kind=w.t_kind.iloc[0],
                         swell_dir_deg=round(w.d.mean()), wind_kmh=round(w.wind_speed_10m.mean(), 1),
                         wind_dir_deg=round(w.wind_direction_10m.mean()), score=round(s, 3), source=w.source.iloc[0]))
c = pd.DataFrame(rows)
c["era_pct"] = c.groupby("source").score.rank(pct=True).round(4)
c = c.sort_values(["era_pct", "score"], ascending=False)
c["rank"] = range(1, len(c) + 1)
c["in_top150"] = c["rank"] <= 150
c.to_csv(out, index=False)
ck = c[c.in_top150].sort_values("date")[["date", "window_local", "swell_height_m", "period_s", "swell_dir_deg", "wind_kmh", "wind_dir_deg", "source", "rank"]].assign(barrelling="", notes="")
ck.to_csv(out.replace(".csv", "_checklist.csv"), index=False)
print("total candidate days", len(c))
c["year"] = pd.to_datetime(c.date).dt.year
print(pd.crosstab(c.year, c.source).assign(top150=c[c.in_top150].groupby("year").size()).fillna(0).astype(int).to_string())
print(c.head(15).drop(columns=["year", "in_top150"]).to_string(index=False))
