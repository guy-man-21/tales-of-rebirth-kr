#!/usr/bin/env python3
# tor_dialogue.xlsx 에서 Korean 빈칸 대사만 모아 씬 단위로 ~400줄 배치 JSON 생성.
import openpyxl, json, os
from pathlib import Path

SRC = r"D:\clean_project\tor_dialogue.xlsx"
OUT = Path(r"D:\clean_project\work\mt")
OUT.mkdir(parents=True, exist_ok=True)
TARGET = 400  # 배치당 목표 줄 수

ws = openpyxl.load_workbook(SRC, read_only=True).active
# 씬별로 빈칸 대사 수집
scenes = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    sc, idv, sp, vo, ty, jp, kr = row[:7]
    if sc is None or idv is None or str(idv).strip() == "":
        continue
    if kr is not None and str(kr).strip() != "":
        continue  # 이미 번역됨(사람 번역/샘플) - 건너뜀
    scenes.setdefault(int(sc), []).append({"scene": int(sc), "id": str(idv), "jp": jp or ""})

# 씬을 순서대로 배치에 담되 ~TARGET 줄에서 끊음(씬은 쪼개지 않음)
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
print(f"배치 {len(batches)}개, 총 {total}줄, 씬 {len(scenes)}개")
