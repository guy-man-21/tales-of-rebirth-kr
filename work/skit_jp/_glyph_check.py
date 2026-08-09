#!/usr/bin/env python3
# 인코딩 가능성 검사: 번역문 kr 의 모든 문자가 빌드(insert) 시 인코딩 되는지.
#  규칙: ASCII(<0x80)는 1바이트 직접 인코딩 -> OK. 그 외 문자는 tbl_full_kr 값집합에
#  있어야 함(2바이트). 없으면 insert 가 cp932 에러/ValueError 로 죽는다.
#  회수 폰트(한글 2350자)에 없는 희귀 음절/기호를 빌드 전에 잡는다.
#  대상: batch_*_kr.json (인자 없으면 전체) + --skits 면 skits/*.json 도.
#  사용: py work\skit_jp\_glyph_check.py [--skits]
import glob
import json
import os
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.join("work", "skit_jp")
TAG = re.compile(r"<[^>]+>")

tbl = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
ENCODABLE = set(tbl.values())  # 2바이트 인코딩 가능 문자
# \n 은 실제 개행(구조), \r 무시. ASCII 제어 제외.


def bad_chars(s):
    # 태그 안쪽은 그대로 두되 검사에서 제외(태그 토큰은 인코더가 별도 처리)
    s = TAG.sub("", s)
    out = []
    for ch in s:
        if ch == "\n":
            continue
        if ord(ch) < 0x80:      # ASCII 1바이트
            continue
        if ch in ENCODABLE:     # TBL 2바이트
            continue
        out.append(ch)
    return out


def scan(files, label):
    total_bad = 0
    charset = {}
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("lines", [])
        for r in rows:
            kr = r.get("kr", "")
            if not kr:
                continue
            bad = bad_chars(kr)
            if bad:
                total_bad += 1
                key = r.get("slot", r.get("scene", "?"))
                if total_bad <= 20:
                    print(f"  [{label}] slot{key} id{r.get('id')}: 미인코딩 {bad}")
                for c in bad:
                    charset[c] = charset.get(c, 0) + 1
    return total_bad, charset


args = sys.argv[1:]
do_skits = "--skits" in args
files = sorted(glob.glob(os.path.join(HERE, "batch_*_kr.json")))
tb, cs = scan(files, "batch")
if do_skits:
    sf = sorted(glob.glob(os.path.join(HERE, "skits", "*.json")))
    tb2, cs2 = scan(sf, "skit")
    tb += tb2
    for c, n in cs2.items():
        cs[c] = cs.get(c, 0) + n

print(f"\n미인코딩 문자 종류: {sorted(cs.items(), key=lambda x:-x[1])}")
print(f"문제 줄: {tb}개")
