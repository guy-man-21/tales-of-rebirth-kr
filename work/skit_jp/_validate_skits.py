#!/usr/bin/env python3
# skits/*.json 코퍼스 최종 검증: jp<->kr 태그 짝, 일본어 잔존, 미인코딩 문자.
#  축약 편집 후 태그 훼손/일본어 재유입을 잡는다. (빈 kr 은 무시)
#  사용: py work\skit_jp\_validate_skits.py
import glob
import json
import os
import re

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TAG = re.compile(r"<[^>]+>")
JPCHAR = re.compile(r"[぀-ゟ゠-ヺ]")   # ・(30FB) ー(30FC) 제외 범위
ENCODABLE = set(json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].values())

tagbad = jpleft = glyphbad = 0
samples = []
for f in sorted(glob.glob("work/skit_jp/skits/*.json")):
    slot = os.path.basename(f)[:-5]
    d = json.load(open(f, encoding="utf-8"))
    for l in d.get("lines", []):
        kr = l.get("kr", "")
        if not kr.strip():
            continue
        jp = l.get("jp", "")
        if sorted(TAG.findall(jp)) != sorted(TAG.findall(kr)):
            tagbad += 1
            if len(samples) < 8:
                samples.append((slot, l["id"], TAG.findall(jp), TAG.findall(kr)))
        if JPCHAR.search(TAG.sub("", kr)):
            jpleft += 1
        for ch in TAG.sub("", kr):
            if ch != "\n" and ord(ch) >= 0x80 and ch not in ENCODABLE:
                glyphbad += 1
                break

print(f"태그불일치 {tagbad} / 일본어잔존 {jpleft} / 미인코딩문자 {glyphbad}")
for s, i, a, b in samples:
    print(f"  slot{s} id{i}: jp{a} != kr{b}")
print("[OK] 문제 없음" if not (tagbad or jpleft or glyphbad) else "[FAIL] 위 문제 수정 필요")
