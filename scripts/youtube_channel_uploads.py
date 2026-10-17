"""Pull every upload of one YouTube channel (cheap: ~1 unit per 50 videos) and merge into youtube_videos.csv.

Usage: python fistral/scripts/youtube_channel_uploads.py <any_video_id_from_the_channel>
Reuses the date / spot / barrel-word extraction from youtube_barrels.py. Key read from fistral/config/youtube_key.txt.
"""
import csv, re, sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve()
src = (HERE.parent / "youtube_barrels.py").read_text(encoding="utf-8")
ns = {"__file__": str(HERE.parent / "youtube_barrels.py"), "__name__": "yb"}
# definitions only (key loading, call(), extraction helpers) - not the search run
exec(src[:src.index("# ---- searches")], ns)
call, written_dates, spot, BARREL_WORDS = ns["call"], ns["written_dates"], ns["spot"], ns["BARREL_WORDS"]
OUT = ns["OUT"]

seed = sys.argv[1]
v0 = call("videos", part="snippet", id=seed)["items"][0]["snippet"]
cid, cname = v0["channelId"], v0["channelTitle"]
uploads = call("channels", part="contentDetails", id=cid)["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

vids, page = [], None
while True:
    p = dict(part="contentDetails", playlistId=uploads, maxResults=50)
    if page:
        p["pageToken"] = page
    r = call("playlistItems", **p)
    vids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]
    page = r.get("nextPageToken")
    if not page:
        break
print(f"channel '{cname}': {len(vids)} uploads")

new = []
for i in range(0, len(vids), 50):
    for v in call("videos", part="snippet,recordingDetails", id=",".join(vids[i:i + 50])).get("items", []):
        s = v["snippet"]
        text = f"{s['title']}\n{s.get('description', '')}"
        published = s["publishedAt"][:10]
        rec = ((v.get("recordingDetails") or {}).get("recordingDate") or "")[:10]
        dates = written_dates(text)
        if dates:
            d, srcd = dates[0], "written_in_title_or_description"
        elif rec:
            d, srcd = rec, "youtube_recording_date"
        elif re.search(r"this morning|today|tonight|this evening|this arvo", text, re.I):
            d, srcd = published, "published_same_day_wording"
        elif re.search(r"yesterday", text, re.I):
            d, srcd = (date.fromisoformat(published) - timedelta(days=1)).isoformat(), "published_minus_1_yesterday"
        else:
            d, srcd = published, "published_unconfirmed"
        new.append(dict(video_id=v["id"], url=f"https://youtu.be/{v['id']}", channel=s["channelTitle"], title=s["title"],
                        published=published, date_extracted=d, date_source=srcd, all_written_dates=";".join(dates),
                        spot=spot(text), barrel_words=";".join(sorted({w.lower() for w in BARREL_WORDS.findall(text)})),
                        query=f"channel uploads: {cname}"))

path = OUT / "youtube_videos.csv"
old = list(csv.DictReader(open(path, encoding="utf-8")))
have = {r["video_id"] for r in old}
added_rows = [r for r in new if r["video_id"] not in have]
allrows = sorted(old + added_rows, key=lambda r: r["date_extracted"])
with open(path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(old[0].keys())); w.writeheader(); w.writerows(allrows)

fist = [r for r in new if r["spot"] != "other"]
bar = [r for r in new if r["barrel_words"]]
print(f"new to csv {len(added_rows)}; channel videos mentioning Fistral {len(fist)}; with barrel words {len(bar)}; "
      f"North/Little Fistral + barrel {sum(r['spot'] in ('North Fistral', 'Little Fistral') for r in bar)}")
for r in sorted(bar, key=lambda r: r["date_extracted"]):
    print(f"{r['date_extracted']} | {r['date_source']} | {r['spot']} | {r['barrel_words']} | {r['title'][:90]}")
