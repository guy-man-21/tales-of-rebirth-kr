#!/usr/bin/env python3
# dbatch_NNN_kr.json -> desc_work.json kr 병합(off). 사용: py work\eboot_jp\_desc_merge.py
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
km = {}
for f in sorted(glob.glob(os.path.join(HERE, "dbatch_[0-9][0-9][0-9]_kr.json"))):
    for r in json.load(open(f, encoding="utf-8")):
        if r.get("kr", "").strip(): km[int(r["off"])] = r["kr"]
p = os.path.join(HERE, "desc_work.json"); rows = json.load(open(p, encoding="utf-8")); n = 0
for r in rows:
    if r["off"] in km and r.get("kr", "") != km[r["off"]]: r["kr"] = km[r["off"]]; n += 1
json.dump(rows, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[OK] {n}행 병합")
