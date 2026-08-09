#!/usr/bin/env python3
# ============================================================
#  _sync.py -- batch_*_kr.json 을 SoT로 삼아 엑셀 Korean 열을 강제 동기화.
#
#  _merge.py 는 "빈 칸만 채움"(기존 번역 보존)이라, 이미 병합된 줄을 나중에
#  _normalize.py 로 고쳐도 엑셀에 반영되지 않는다. 이 스크립트가 그 갭을 메운다.
#
#  MT 배치에 없는 줄(사람이 직접 넣은 번역 등)은 건드리지 않는다.
# ============================================================
import glob
import json
import re

import openpyxl

XLSX = r"D:\clean_project\tor_dialogue.xlsx"
MTDIR = r"D:\clean_project\work\mt"
TAG = re.compile(r"<[^>]+>")

kr = {}
for f in sorted(glob.glob(f"{MTDIR}/batch_*_kr.json")):
    for r in json.load(open(f, encoding="utf-8")):
        kr[(int(r["scene"]), str(r["id"]))] = r.get("kr", "")
print(f"[i] MT 결과 {len(kr)}줄 로드")

wb = openpyxl.load_workbook(XLSX)
ws = wb.active
changed = same = tagwarn = 0
warn = []
for row in ws.iter_rows(min_row=2):
    sc, idv = row[0].value, row[1].value
    if sc is None or idv is None or str(idv).strip() == "":
        continue
    key = (int(sc), str(idv))
    if key not in kr:
        continue
    new = kr[key]
    if (row[6].value or "") == new:
        same += 1
        continue
    jp = row[5].value or ""
    if sorted(TAG.findall(jp)) != sorted(TAG.findall(new)):
        tagwarn += 1
        if len(warn) < 10:
            warn.append((sc, idv, TAG.findall(jp), TAG.findall(new)))
    row[6].value = new
    changed += 1
wb.save(XLSX)

print(f"[동기화] 갱신 {changed}줄, 이미 동일 {same}줄, 태그경고 {tagwarn}건")
if warn:
    print("[태그경고 샘플]")
    for sc, idv, a, b in warn:
        print(f"  s{sc} #{idv}: jp{a} != kr{b}")
