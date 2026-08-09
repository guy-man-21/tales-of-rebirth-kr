#!/usr/bin/env python3
# 축약 patch를 translation/*.json 에 반영 (태그/일본어/길이 검증)
import glob
import json
import os
import re

os.chdir(r"D:\clean_project")
TAG = re.compile(r"<[^>]+>")
JP = re.compile(r"[぀-ゟ゠-ヺ㐀-䶿一-鿿]")


def blen(s):
    return sum(1 if ord(c) < 128 else 2 for c in s)


patches = {}
for f in sorted(glob.glob("work/shrink_jp/patch_*.json")):
    for r in json.load(open(f, encoding="utf-8")):
        patches[(int(r["scene"]), str(r["id"]))] = r["kr"]
print(f"[i] 패치 {len(patches)}줄")

applied = 0
rej = []
by_scene = {}
for f in sorted(glob.glob("translation/*.json")):
    sc = int(os.path.basename(f).replace(".json", "")) if os.path.basename(f).replace(".json", "").isdigit() else None
    if sc is None:
        continue
    d = json.load(open(f, encoding="utf-8"))
    dirty = False
    for l in d.get("lines", []):
        key = (sc, str(l["id"]))
        if key not in patches:
            continue
        old = l.get("kr") or ""
        new = patches[key]
        if sorted(TAG.findall(old)) != sorted(TAG.findall(new)):
            rej.append((key, "태그 불일치"))
            continue
        if JP.search(TAG.sub("", new)):
            rej.append((key, "일본어 유입"))
            continue
        if blen(new) >= blen(old):
            rej.append((key, "안 줄어듦"))
            continue
        l["kr"] = new
        applied += 1
        dirty = True
    if dirty:
        json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"[적용] {applied}줄, 거부 {len(rej)}줄")
for k, why in rej[:15]:
    print(f"  거부 s{k[0]} #{k[1]}: {why}")
