#!/usr/bin/env python3
# out_NNN.json (번역결과) -> slot2_work.json 병합 + 태그/바이트 검증
import glob
import json
import os
import re
import struct

os.chdir(r"D:\clean_project")
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
TAG = re.compile(r"<[0-9A-Fa-f]{2,4}>")
TAG4 = re.compile(r"<([0-9A-Fa-f]{4})>")
TAG2 = re.compile(r"<([0-9A-Fa-f]{2})>")


def enc_len(s):
    n = 0
    i = 0
    while i < len(s):
        m = TAG4.match(s, i)
        if m:
            n += 2
            i = m.end()
            continue
        m = TAG2.match(s, i)
        if m:
            n += 1
            i = m.end()
            continue
        c = s[i]
        n += 1 if ord(c) < 0x80 else 2
        i += 1
    return n


res = {}
for f in sorted(glob.glob("work/battle_jp/out_*.json")):
    for r in json.load(open(f, encoding="utf-8")):
        res[int(r["off"])] = r["kr"]
print(f"결과 {len(res)}개")

rows = json.load(open("work/battle_jp/slot2_work.json", encoding="utf-8"))
ok = tagbad = overbad = 0
probs = []
for r in rows:
    off = int(r["off"])
    if off not in res or (r.get("kr") or "").strip():
        continue
    kr = res[off]
    if TAG.findall(r["jp"]) != TAG.findall(kr):
        tagbad += 1
        probs.append((off, "태그", r["jp"][:26], kr[:26]))
        continue
    if enc_len(kr) + 1 > r["avail"]:
        overbad += 1
        probs.append((off, f"초과 {enc_len(kr)+1}>{r['avail']}", r["jp"][:26], kr[:26]))
        continue
    r["kr"] = kr
    r["src"] = "agent"
    ok += 1

json.dump(rows, open("work/battle_jp/slot2_work.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
left = sum(1 for r in rows if not (r.get("kr") or "").strip())
print(f"병합 OK {ok} / 태그거부 {tagbad} / 초과거부 {overbad} / 남은 미번역 {left}")
for off, why, jp, kr in probs[:20]:
    print(f"  @{off} [{why}] jp={jp!r} kr={kr!r}")
