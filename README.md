# Surf Shape Forecaster — North Fistral, Newquay

Goal: learn **when North Fistral barrels**. The idea is to match dated "barrelling" sightings (social posts, YouTube clips)
to that day's swell, wind and tide, and to the shape of the seafloor and sandbars, and eventually train a neural network that
predicts barrel days.

This repo holds the code, the study-area outlines and the labels and checklists. The large raw data is **not** included
(see [Re-downloading the raw data](#re-downloading-the-raw-data)).

## Current status (17 Oct 2026)

- **Seafloor and beach data:** 70 survey datasets from 2007 to 2026 (beach profiles, lidar and a 2007 boat survey), plus EMODnet,
  all clipped to the study area. The v3 area covers all of Fistral, with zones `little` / `north` / `south` / `offshore`.
- **Conditions:** hourly waves, swell and wind from Oct 2016 to Oct 2026 (Open-Meteo). ERA5-Ocean fills the 2016–2021 wave gap.
- **Barrel labels:** only **4 days** so far (`data/labels/barrel_days.csv`), 2 of them confident:
  - 2020-09-13 North Fistral (high)
  - 2021-02-13 Little Fistral (medium)
  - 2022-02-27 Little Fistral / Fistral (medium)
  - 2017-09-17 Fistral contest (low)
- **To do (needs a human):** fill in the `barrelling` column (yes / no / unsure) in
  - `data/labels/candidate_days_checklist.csv`: 150 forecast-shortlisted days to check against the Facebook groups
  - `data/labels/youtube_checklist.csv`: 259 dated Fistral YouTube videos to watch
  
  The aim is 50–100+ confirmed barrel days, plus confirmed "no" days, before training anything.

## Folder layout

```
scripts/          processing code (run in order, see below)
data/areas/       study-area outlines (GeoJSON, lon/lat WGS84)
                    fistral_area_v1  original North Fistral trapezium
                    fistral_area_v2  shore edge moved 225 m inland to the back of the beach
                    fistral_area_v3  all of Fistral (Little / North / South + offshore), shore edge follows the back of the beach
data/labels/      barrel_days.csv, candidate_days.csv (+ checklist), youtube_checklist.csv
data/surveys/     index.csv: one row per survey (date, type, points, height range, coverage for v1 / v2 / v3 and per zone)
docs/             plan.md, survey_download_guide.md
```

## Pipeline (how to re-run)

Python 3.11+ with `pip install -r requirements.txt`. The scripts were written on the original PC and some still have
hard-coded `C:\Users\...` paths at the top, so edit those paths before running anywhere else.

| Step | Script | Input → output |
|---|---|---|
| 1 | `01_emodnet_clip_v1.py` | EMODnet GeoTIFF → clipped lon, lat, depth CSV |
| 2–4 | `02/03/04_cco_surveys_clip_*.py` | CCO survey download (unzipped) → per-survey folders, `*_clipped[_v2/_v3].csv`, `index.csv`. v3 adds the `zone` column and EMODnet |
| 5 | `05_openmeteo_conditions.py` | Open-Meteo marine and archive APIs → `conditions_hourly.csv` |
| 6 | `06_era5_wave_backfill.py` | Open-Meteo ERA5-Ocean → `conditions_hourly_era5.csv` (+ comparison stats) |
| 7 | `07_candidate_days.py` | conditions → `candidate_days.csv` + checklist (rule-based shortlist, **not** labels) |
| — | `youtube_barrels.py` | YouTube Data API v3 search → `youtube_videos.csv`, adds confident days to `barrel_days.csv` (resumable, about 80 searches/day) |
| — | `youtube_channel_uploads.py <video_id>` | every upload of one channel → merged into `youtube_videos.csv` |

**YouTube key:** put your own YouTube Data API v3 key in `config/youtube_key.txt` (git-ignored). Never put it in code.

## Data sources and credits

- **Channel Coastal Observatory / South West Coastal Monitoring** (coastalmonitoring.org): beach topographic surveys, lidar
  and bathymetry. Free to use; please credit *"Channel Coastal Observatory"*. Downloaded by hand from the portal; their
  terms don't allow automated scraping.
- **EMODnet Bathymetry**: DTM 2024 (emodnet:mean), via the EMODnet WCS service.
- **Open-Meteo**: marine (waves/swell), ERA5-Ocean and historical weather (wind) APIs. Licence **CC BY 4.0**, *"Weather data by Open-Meteo.com"*.
- **YouTube Data API v3**: video titles, descriptions and dates (public metadata only).
- **OpenStreetMap** contributors (ODbL): Fistral Beach end points, used to set zone boundaries.

Facebook and Instagram content is **not** collected automatically, because Meta's terms don't allow it. Labels from those come from
posts the user reads and pastes in by hand, and the raw pasted text is not stored in this repo.

## Re-downloading the raw data

Not in git (size and licence): CCO survey zip and unpacked files, per-survey clipped point CSVs, GeoTIFFs, hourly
conditions CSVs, the YouTube video list and progress file, and pasted social-media text.

1. **CCO surveys:** see `docs/survey_download_guide.md`. Download into `data/bathymetry/surveys/raw/`, then run steps 2–4.
2. **EMODnet:** WCS GetCoverage for `emodnet:mean`, EPSG:4326, BBOX `-5.165,50.400,-5.085,50.445`, GeoTIFF (see `scripts/01_*`).
3. **Conditions:** run steps 5 and 6. Free, no key needed.
4. **YouTube:** add your key, then run `youtube_barrels.py` (two days because of quota) and `youtube_channel_uploads.py sFRBTcGE_2M`.

Heights are metres relative to Ordnance Datum Newlyn (ODN). Survey coordinates are British National Grid (EPSG:27700).
EMODnet depths are negative below the vertical datum.
