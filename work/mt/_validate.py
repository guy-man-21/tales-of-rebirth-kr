#!/usr/bin/env python3
# MT 결과(batch_NNN_kr.json) 검증: JSON 유효성, 줄수/id 일치, 태그 짝, 미번역 잔존.
# 사용: py work\mt\_validate.py [batch_044 batch_047 ...]   (인자 없으면 전체)
import glob
import json
import os
import re
import sys

MTDIR = r"D:\clean_project\work\mt"
TAG = re.compile(r"<[^>]+>")
# 히라가나/가타카나 잔존 탐지.
# U+30FB(가운뎃점 ・)와 U+30FC(장음 ー)는 카타카나 블록이지만 원문에도 정상적으로
# 쓰이는 구분자/기호라 제외한다. 안 그러면 <Annie>・바스 같은 정상 줄을 오탐한다.
JPCHAR = re.compile(r"[぀-ゟ゠-ヺ]")

names = sys.argv[1:]
if not names:
    names = [os.path.basename(f).replace(".json", "")
             for f in sorted(glob.glob(os.path.join(MTDIR, "batch_[0-9][0-9][0-9].json")))]

total_bad = 0
for n in names:
    src = os.path.join(MTDIR, n + ".json")
    dst = os.path.join(MTDIR, n + "_kr.json")
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

    by_key = {(int(r["scene"]), str(r["id"])): r.get("kr", "") for r in res}
    missing = tagbad = jpleft = empty = 0
    tag_samples = []
    for l in lines:
        key = (int(l["scene"]), str(l["id"]))
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
        # 태그 제거 후 일본어 문자가 남아있으면 미번역 의심
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
            print(f"         s{key[0]} id{key[1]}: jp{a} != kr{b}")
    else:
        print(f"[OK]   {n}: {len(res)}줄")

print(f"\n검증 결과: 문제 배치 {total_bad}개")
