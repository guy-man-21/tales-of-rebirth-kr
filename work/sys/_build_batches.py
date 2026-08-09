#!/usr/bin/env python3
# tor_system.xlsx (표시/시스템 10,555줄) 에서 '번역 대상'만 골라 배치 JSON 생성.
#
# 번역 대상 기준:
#   - jp 에 CJK(히라가나/가타카나/한자/한글) 가 하나라도 있어야 함.
#   - ASCII/기호만인 줄(엔진 내부 라벨/디버그: notice, MAP-NO=%d, <unk17:...> 등)은 제외.
#     -> 배치에 안 넣으면 kr 이 비어 빌드가 원문(CN)을 그대로 유지한다(안전).
#   - jp 빈 줄 제외.
#   - 빌드 불가 씬(225/226/227 비SCPK, 4444 파싱불가) 제외.
#
# 대사 파이프라인(work/mt)과 형식 동일. 출력: work/sys/batch_NNN.json
import openpyxl, json
from pathlib import Path

SRC = r"D:\clean_project\tor_system.xlsx"
OUT = Path(r"D:\clean_project\work\sys")
OUT.mkdir(parents=True, exist_ok=True)
TARGET = 300  # 배치당 목표 줄 수 (시스템 문자열은 태그가 많아 대사보다 작게)
SKIP_SCENES = {225, 226, 227, 4444}

def has_cjk(s):
    return any('぀' <= c <= 'ヿ' or '㐀' <= c <= '鿿'
               or '가' <= c <= '힣' for c in s)

ws = openpyxl.load_workbook(SRC, read_only=True).active
scenes = {}
skipped_ascii = skipped_empty = 0
for row in ws.iter_rows(min_row=2, values_only=True):
    sc, idv, sp, vo, ty, jp, kr = row[:7]
    if sc is None or idv is None or str(idv).strip() == "":
        continue  # 씬 헤더행
    if int(sc) in SKIP_SCENES:
        continue
    if kr is not None and str(kr).strip() != "":
        continue  # 이미 번역됨
    jp = jp or ""
    if not jp.strip():
        skipped_empty += 1
        continue
    if not has_cjk(jp):
        skipped_ascii += 1
        continue  # ASCII/기호만 -> 내부 라벨, 원문 유지
    scenes.setdefault(int(sc), []).append(
        {"scene": int(sc), "id": str(idv), "jp": jp})

batches, cur = [], []
for sc in sorted(scenes):
    if cur and len(cur) + len(scenes[sc]) > TARGET:
        batches.append(cur); cur = []
    cur.extend(scenes[sc])
if cur:
    batches.append(cur)

for i, b in enumerate(batches):
    json.dump({"batch": i, "lines": b},
              open(OUT / f"batch_{i:03d}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

total = sum(len(b) for b in batches)
print(f"배치 {len(batches)}개, 번역대상 {total}줄, 씬 {len(scenes)}개")
print(f"제외: ASCII/기호만 {skipped_ascii}줄, 빈줄 {skipped_empty}줄")
