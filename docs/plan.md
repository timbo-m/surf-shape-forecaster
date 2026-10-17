# Plan

1. **Seafloor shape:** EMODnet for the deep water, plus Channel Coastal Observatory beach surveys and lidar for the sandbars
   (spring and autumn, 2007–2026). All of it is clipped to the Fistral study area (v3: Little / North / South / offshore zones).
2. **Conditions:** hourly swell height, period and direction, plus wind (Open-Meteo, 2016–2026). Tide still needs adding:
   the modelled sea level only starts in Nov 2022, so a tide gauge or tide predictions are wanted.
3. **Labels:** dated barrel sightings from YouTube (via the API), and from Facebook and Instagram posts that the user reads
   and pastes in by hand. Days the model thinks are likely barrelling (`candidate_days.csv`) are used only to decide which
   dates to check, never as labels.
4. **Dataset:** one row per day (or per tide window), joining conditions, the nearest earlier survey's bar shape and the label
   (barrel / no barrel / unknown).
5. **Model:** start simple (logistic regression or gradient boosting), then a small neural network once there are enough
   labelled days. Use time-based train and test splits.

Open issues:
- Too few labels so far (4). Filling in the two checklists is the bottleneck.
- No lidar south of grid line N 62000 (tile SW7961). It can be downloaded from CCO.
- Little Fistral has no spring/autumn beach surveys. Only the lidar and the 2007 boat survey cover it.
