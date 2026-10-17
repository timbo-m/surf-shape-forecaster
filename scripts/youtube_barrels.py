"""Find dated Fistral barrel sessions on YouTube via the official YouTube Data API v3.

Setup: save your API key (just the key, one line) in fistral/config/youtube_key.txt
Run:   python fistral/scripts/youtube_barrels.py   (run again on later days to continue; it resumes)

Quota: search.list costs 100 of the free 10,000 daily units, so each run does at most 80 searches.
Progress is saved in fistral/data/posts/youtube_progress.json.

Outputs (fistral/data/posts/):
    youtube_videos.csv  - every video found, with extracted date, spot and barrel words
    barrel_days.csv     - confident Fistral barrel sessions appended (no duplicates)
"""
import csv, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / "config" / "youtube_key.txt"
OUT = ROOT / "data" / "posts"
PROGRESS = OUT / "youtube_progress.json"
API = "https://www.googleapis.com/youtube/v3/"
MAX_SEARCHES = 80

QUERIES = ["Fistral barrel", "North Fistral", "Little Fistral", "Fistral barrel of the day", "Fistral pumping",
           "Fistral tube", "Fistral pitted", "Newquay barrel", "Fistral bodyboard", "Fistral surf"]
YEARS = list(range(2016, date.today().year + 1))

BARREL_WORDS = re.compile(r"(?<![a-z])(?:barrel\w*|tube[ds]?|tubing|pitted|keg\w*|slab\w*|cover[- ]?up)", re.I)  # not "youtube"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

key = KEY_FILE.read_text().strip() if KEY_FILE.exists() else ""
if not key:
    sys.exit(f"No API key found. Save your YouTube Data API key in {KEY_FILE}")


class QuotaExceeded(Exception):
    pass


def call(endpoint, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode({**params, "key": key})
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace").replace(key, "<key>")
            if e.code == 403 and "quota" in body.lower():
                raise QuotaExceeded
            if e.code in (400, 401, 403):
                sys.exit(f"YouTube API error {e.code}: {body[:400]}")
            time.sleep(2 ** (i + 1))
        except urllib.error.URLError:
            time.sleep(2 ** (i + 1))
    sys.exit(f"YouTube API {endpoint} failed after retries")


def written_dates(text):
    """Explicit calendar dates in text, UK day-first (13 09 2020, 13/09/20, 13th Sept 2020, Sept 13 2020)."""
    found = re.findall(r"(?<!\d)(\d{1,2})[ ./-](\d{1,2})[ ./-](\d{4}|\d{2})(?!\d)", text)
    found += [(d, MONTHS[m[:3].lower()], y) for d, m, y in re.findall(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(\d{4})\b", text, re.I)]
    found += [(d, MONTHS[m[:3].lower()], y) for m, d, y in re.findall(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", text, re.I)]
    out = set()
    for d, m, y in found:
        y = int(y) + (2000 if len(str(y)) == 2 else 0)
        try:
            dt = date(y, int(m), int(d))
        except ValueError:
            continue
        if date(2005, 1, 1) <= dt <= date.today():
            out.add(dt.isoformat())
    return sorted(out)


def spot(text):
    if re.search(r"little\s+fistral", text, re.I): return "Little Fistral"
    if re.search(r"north\s+(fistral|fizzy)", text, re.I): return "North Fistral"
    if re.search(r"south\s+(fistral|fizzy)", text, re.I): return "South Fistral"
    if re.search(r"fistral|fizzy", text, re.I): return "Fistral"
    return "other"


# ---- searches (resumable) ----
state = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {"done": [], "pending_page": {}, "ids": {}}
tasks = [f"{q}|{y}" for q in QUERIES for y in YEARS]
SKIP_SEARCH = "--no-search" in sys.argv  # rebuild outputs from saved video ids without spending search quota
searches = 0
try:
    for t in tasks:
        if SKIP_SEARCH or t in state["done"]:
            continue
        q, y = t.split("|")
        page = state["pending_page"].get(t)
        while searches < MAX_SEARCHES:
            params = dict(part="id", q=q, type="video", maxResults=50, order="date",
                          publishedAfter=f"{y}-01-01T00:00:00Z", publishedBefore=f"{int(y) + 1}-01-01T00:00:00Z")
            if page:
                params["pageToken"] = page
            r = call("search", **params)
            searches += 1
            for it in r.get("items", []):
                state["ids"].setdefault(it["id"]["videoId"], q)
            page = r.get("nextPageToken")
            print(f"search {searches}: '{q}' {y} -> {len(r.get('items', []))} (unique videos {len(state['ids'])})", flush=True)
            if not page:
                break
        if page:
            state["pending_page"][t] = page
            break
        state["pending_page"].pop(t, None)
        state["done"].append(t)
        if searches >= MAX_SEARCHES:
            break
except QuotaExceeded:
    print("Daily quota used up - run again tomorrow to continue.")
OUT.mkdir(parents=True, exist_ok=True)
PROGRESS.write_text(json.dumps(state))
remaining = len([t for t in tasks if t not in state["done"]])

# ---- details for every video found so far (1 unit per 50 videos) ----
rows, ids = [], list(state["ids"])
try:
    for i in range(0, len(ids), 50):
        for v in call("videos", part="snippet,recordingDetails", id=",".join(ids[i:i + 50])).get("items", []):
            s = v["snippet"]
            text = f"{s['title']}\n{s.get('description', '')}"
            published = s["publishedAt"][:10]
            rec = ((v.get("recordingDetails") or {}).get("recordingDate") or "")[:10]
            dates = written_dates(text)
            if dates:
                d, src = dates[0], "written_in_title_or_description"
            elif rec:
                d, src = rec, "youtube_recording_date"
            elif re.search(r"this morning|today|tonight|this evening|this arvo", text, re.I):
                d, src = published, "published_same_day_wording"
            elif re.search(r"yesterday", text, re.I):
                d, src = (date.fromisoformat(published) - timedelta(days=1)).isoformat(), "published_minus_1_yesterday"
            else:
                d, src = published, "published_unconfirmed"
            words = sorted({w.lower() for w in BARREL_WORDS.findall(text)})
            rows.append(dict(video_id=v["id"], url=f"https://youtu.be/{v['id']}", channel=s["channelTitle"],
                             title=s["title"], published=published, date_extracted=d, date_source=src,
                             all_written_dates=";".join(dates), spot=spot(text), barrel_words=";".join(words),
                             query=state["ids"][v["id"]]))
except QuotaExceeded:
    print("Quota ran out while fetching video details - run again tomorrow.")

cols = ["video_id", "url", "channel", "title", "published", "date_extracted", "date_source",
        "all_written_dates", "spot", "barrel_words", "query"]
# keep rows added by other scripts (e.g. youtube_channel_uploads.py) that aren't in the search state
vpath = OUT / "youtube_videos.csv"
if vpath.exists():
    have = {r["video_id"] for r in rows}
    rows += [r for r in csv.DictReader(open(vpath, encoding="utf-8")) if r["video_id"] not in have]
rows.sort(key=lambda r: r["date_extracted"])
with open(OUT / "youtube_videos.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

# ---- confident barrel sessions -> barrel_days.csv ----
CONF = {"written_in_title_or_description": "high", "youtube_recording_date": "medium", "published_same_day_wording": "medium"}
bd = OUT / "barrel_days.csv"
existing = bd.read_text(encoding="utf-8-sig") if bd.exists() else ""
seen = {f"{x['date']}|{x['notes'].split(';')[0].split(' =')[0]}" for x in csv.DictReader(existing.splitlines())} if existing else set()
added = 0
with open(bd, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    for r in rows:
        if r["spot"] not in ("North Fistral", "Little Fistral") or not r["barrel_words"] or r["date_source"] not in CONF:
            continue
        if r["video_id"] in existing or f"{r['date_extracted']}|{r['spot']}" in seen:
            continue
        w.writerow([r["date_extracted"], "", r["date_source"], f"YouTube: {r['title']} ({r['url']})",
                    r["barrel_words"], r["title"], CONF[r["date_source"]], r["spot"]])
        seen.add(f"{r['date_extracted']}|{r['spot']}")
        added += 1

fist = [r for r in rows if r["spot"] != "other"]
print(f"run searches {searches}; tasks left {remaining}/{len(tasks)}; videos {len(rows)}; "
      f"Fistral videos {len(fist)}; Fistral+barrel words {sum(bool(r['barrel_words']) for r in fist)}; "
      f"added to barrel_days.csv {added}")
