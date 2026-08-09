#!/usr/bin/env python3
# tbatch_NNN_kr.json ([{off,kr}]) 을 eboot_work.json 의 kr 에 병합(off 기준).
#  사용: py work\eboot_jp\_title_merge.py
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
kr_map = {}
patterns = ["tbatch_[0-9][0-9][0-9]_kr.json", "cbatch_[0-9][0-9][0-9]_kr.json"]
files = sorted(f for pat in patterns for f in glob.glob(os.path.join(HERE, pat)))
for f in files:
    for r in json.load(open(f, encoding="utf-8")):
        if r.get("kr", "").strip():
            kr_map[int(r["off"])] = r["kr"]

p = os.path.join(HERE, "eboot_work.json")
rows = json.load(open(p, encoding="utf-8"))
n = 0
for r in rows:
    if r["off"] in kr_map and r.get("kr", "") != kr_map[r["off"]]:
        r["kr"] = kr_map[r["off"]]
        n += 1
json.dump(rows, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[OK] {n}행 kr 병합")
