#!/usr/bin/env python3
# 스킷 MT 결과(batch_NNN_kr.json) 검증: JSON/줄수/id 일치, 태그 짝, 일본어 잔존, 빈번역.
#  사용: py work\skit_jp\_validate.py [batch_001 ...]
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TAG = re.compile(r"<[^>]+>")
# U+30FB(・) U+30FC(ー)는 구분자/기호로 정상 사용 -> 잔존 탐지에서 제외
JPCHAR = re.compile(r"[぀-ゟ゠-ヺ]")

names = sys.argv[1:]
if not names:
    names = [os.path.basename(f)[:-5]
             for f in sorted(glob.glob(os.path.join(HERE, "batch_[0-9][0-9][0-9].json")))]

total_bad = 0
for n in names:
    src = os.path.join(HERE, n + ".json")
    dst = os.path.join(HERE, n + "_kr.json")
    if not os.path.exists(dst):
        continue
    try:
        lines = json.load(open(src, encoding="utf-8"))["lines"]
        res = json.load(open(dst, encoding="utf-8"))
    except Exception as e:
        print(f"[FAIL] {n}: JSON 파싱 실패 {type(e).__name__}: {e}")
        total_bad += 1
        continue

    errs = []
    if len(res) != len(lines):
        errs.append(f"줄수 {len(res)} != 입력 {len(lines)}")

    by_key = {(int(r["slot"]), str(r["id"])): r.get("kr", "") for r in res}
    missing = tagbad = jpleft = empty = 0
    tag_samples = []
    for l in lines:
        key = (int(l["slot"]), str(l["id"]))
        if key not in by_key:
            missing += 1
            continue
        kr = by_key[key]
        jp = l["jp"]
        if not kr.strip():
            empty += 1
        if sorted(TAG.findall(jp)) != sorted(TAG.findall(kr)):
            tagbad += 1
            if len(tag_samples) < 3:
                tag_samples.append((key, TAG.findall(jp), TAG.findall(kr)))
        if JPCHAR.search(TAG.sub("", kr)):
            jpleft += 1
    if missing:
        errs.append(f"누락 {missing}줄")
    if tagbad:
        errs.append(f"태그불일치 {tagbad}줄")
    if empty:
        errs.append(f"빈번역 {empty}줄")
    if jpleft:
        errs.append(f"일본어잔존 {jpleft}줄")

    if errs:
        total_bad += 1
        print(f"[FAIL] {n}: {', '.join(errs)}")
        for key, a, b in tag_samples:
            print(f"         slot{key[0]} id{key[1]}: jp{a} != kr{b}")
    else:
        print(f"[OK]   {n}: {len(res)}줄")

print(f"\n검증 결과: 문제 배치 {total_bad}개")
