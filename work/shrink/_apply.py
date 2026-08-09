#!/usr/bin/env python3
# ============================================================
#  _apply.py -- 줄이기 패치(patch_NNN.json)를 엑셀(SoT)에 반영
#
#  검증 후 반영한다. 하나라도 어기면 그 줄은 거부:
#    - 태그 집합/개수가 원래 kr 과 달라짐 (크래시)
#    - 일본어 문자 유입
#    - 오히려 길어짐 (줄이러 왔는데)
#
#  반영 후 theirsce_xlsx.py import 로 translation/*.json 재생성할 것.
# ============================================================
import glob
import json
import os
import re

import openpyxl

os.chdir(r"D:\clean_project")
TAG = re.compile(r"<[^>]+>")
JP = re.compile(r"[぀-ゟ゠-ヺ㐀-䶿一-鿿]")


def blen(s):
    return sum(1 if ord(c) < 128 else 2 for c in s)


patches = {}
for f in sorted(glob.glob("work/shrink/patch_*.json")):
    for r in json.load(open(f, encoding="utf-8")):
        patches[(int(r["scene"]), str(r["id"]))] = r["kr"]
print(f"[i] 패치 {len(patches)}줄 ({len(glob.glob('work/shrink/patch_*.json'))}개 파일)")

wb = openpyxl.load_workbook("tor_dialogue.xlsx")
ws = wb.active
applied = 0
rej = []
saved = {}

for row in ws.iter_rows(min_row=2):
    sc, idv = row[0].value, row[1].value
    if sc is None or idv is None or str(idv).strip() == "":
        continue
    key = (int(sc), str(idv))
    if key not in patches:
        continue
    old = row[6].value or ""
    new = patches[key]

    if sorted(TAG.findall(old)) != sorted(TAG.findall(new)):
        rej.append((key, "태그 불일치"))
        continue
    if JP.search(TAG.sub("", new)):
        rej.append((key, "일본어 문자 유입"))
        continue
    d = blen(old) - blen(new)
    if d <= 0:
        rej.append((key, f"안 줄어듦 ({d}B)"))
        continue

    row[6].value = new
    applied += 1
    saved[key[0]] = saved.get(key[0], 0) + d

wb.save("tor_dialogue.xlsx")

# 배치 파일(kr)에도 같은 내용을 반영한다.
# 안 그러면 나중에 _sync.py 를 돌릴 때 배치가 엑셀을 덮어써 축약이 되돌아간다.
accepted = {k for k in patches if k not in {r[0] for r in rej}}
bfiles = 0
for f in sorted(glob.glob("work/mt/batch_*_kr.json")):
    data = json.load(open(f, encoding="utf-8"))
    dirty = False
    for r in data:
        k = (int(r["scene"]), str(r["id"]))
        if k in accepted and r.get("kr") != patches[k]:
            r["kr"] = patches[k]
            dirty = True
    if dirty:
        bfiles += 1
        json.dump(data, open(f, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
print(f"[배치 반영] {bfiles}개 파일")

print(f"[적용] {applied}줄, 거부 {len(rej)}줄")
for k, why in rej[:15]:
    print(f"  거부 s{k[0]} #{k[1]}: {why}")

need = {r["scene"]: r["over"] for r in json.load(open("overflow.json",
                                                     encoding="utf-8"))}
short = [(sc, need[sc], saved.get(sc, 0)) for sc in sorted(need)
         if saved.get(sc, 0) < need[sc]]
print(f"\n[씬별] 목표 미달 {len(short)} / {len(need)}")
for sc, n, s in short[:20]:
    print(f"  씬 {sc}: 필요 {n}B, 절약 {s}B")
