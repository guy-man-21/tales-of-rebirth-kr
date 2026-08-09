#!/usr/bin/env python3
# ============================================================
#  _prep.py -- 초과 씬별 '줄이기 작업 지시서' 생성
#
#  DAT 레이아웃은 못 바꾸므로(EBOOT 2차 오프셋 테이블) 각 씬 THEIRSCE 는
#  원본 블롭 크기 안에 들어가야 한다. overflow.json 의 초과 바이트만큼 줄인다.
#  한글 1자 = 2바이트. 여유 2자를 더 잡는다.
#
#  출력: work/shrink/task_{NNN}.json  (에이전트 1명이 맡을 씬 묶음)
# ============================================================
import json
import math
import os
from pathlib import Path

os.chdir(r"D:\clean_project")
OUT = Path("work/shrink")
OUT.mkdir(parents=True, exist_ok=True)

over = json.load(open("overflow.json", encoding="utf-8"))
over.sort(key=lambda r: r["scene"])

PER_TASK = 15
tasks = []
cur = []

for r in over:
    sc = r["scene"]
    cut_chars = math.ceil(r["over"] / 2) + 2   # 한글 1자=2B, 여유 2자
    d = json.load(open(f"translation/{sc}.json", encoding="utf-8"))
    lines = [{"id": str(l["id"]), "jp": l.get("jp", ""), "kr": l.get("kr", "")}
             for l in d.get("lines", []) if (l.get("kr") or "").strip()]
    # 긴 줄부터 (줄일 후보)
    lines.sort(key=lambda x: -len(x["kr"]))
    cur.append({"scene": sc, "over_bytes": r["over"],
                "cut_chars": cut_chars, "lines": lines[:12]})
    if len(cur) >= PER_TASK:
        tasks.append(cur)
        cur = []
if cur:
    tasks.append(cur)

for i, t in enumerate(tasks):
    json.dump({"task": i, "scenes": t},
              open(OUT / f"task_{i:03d}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

tot = sum(len(t) for t in tasks)
print(f"[OK] 작업 {len(tasks)}개, 씬 {tot}개 -> work/shrink/task_NNN.json")
print(f"     줄일 글자수 합계 약 {sum(math.ceil(r['over']/2)+2 for r in over)}자")
