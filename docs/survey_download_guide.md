# Downloading the Fistral beach surveys (Channel Coastal Observatory)

Free, but download by hand: the portal's terms don't allow robots or scraping.

1. Open https://coastalmonitoring.org/cco/ (you only need to register to save searches).
2. Use **Zoom to location** and go to Fistral, Newquay.
3. **Create Selection:** click around the area (use `data/areas/fistral_area_v3.geojson` as a guide, drawing it slightly
   bigger), then double-click to close the shape.
4. **View Results:** tick *Topographic survey*, *Bathymetry* and *Lidar*, set the dates (e.g. 01/01/2007 to today), then **Apply Filter**.
5. In the **Results** tab, tick everything on each data-type tab, then **Basket**, **Download**, fill in the form and **Submit**.
6. Save the zip into `data/bathymetry/surveys/raw/` and run `scripts/02…04_cco_surveys_clip_*.py`.

What you get: tab-separated text files (`Easting, Northing, Elevation_OD`; older files say `Elevation`) in British National
Grid with heights in metres relative to ODN, plus lidar grids (`.asc`/`.tif`, 1 m; `…lidarf` = bare ground, `…lidaru` = unfiltered).
File codes: `tip` = spring/autumn interim profiles, `tb` = full baseline survey, `tp` = profiles, `tpsp` / `tstr` = post-storm.

Also worth grabbing from the same site: lidar tile **SW7961** (South Fistral), the Perranporth wave buoy and tide data.

Credit: "Channel Coastal Observatory" / South West Coastal Monitoring.
