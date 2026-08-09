#!/usr/bin/env python3
# JP 빌드 초과 씬의 번역 축약 지시서 생성 (translation 기준)
# 초과바이트 -> 줄일 한글자 = ceil(초과/2) + 여유. JP 압축이라 넉넉히.
import json
import math
import os
from pathlib import Path

os.chdir(r"D:\clean_project")
OUT = Path("work/shrink_jp")
OUT.mkdir(parents=True, exist_ok=True)

rep = json.load(open("build_jp_report.json", encoding="utf-8"))
over = sorted(rep["over"], key=lambda o: o["scene"])
print(f"초과 {len(over)}씬")

PER = 12
tasks = []
cur = []
for r in over:
    sc = r["scene"]
    cut = math.ceil(r["over"] / 2) + 4   # 여유 4자 (압축 변동 대비)
    d = json.load(open(f"translation/{sc}.json", encoding="utf-8"))
    lines = [{"id": str(l["id"]), "jp": l.get("jp", ""), "kr": l.get("kr", "")}
             for l in d["lines"] if (l.get("kr") or "").strip()]
    lines.sort(key=lambda x: -len(x["kr"]))
    cur.append({"scene": sc, "over_bytes": r["over"], "cut_chars": cut,
                "lines": lines[:14]})
    if len(cur) >= PER:
        tasks.append(cur)
        cur = []
if cur:
    tasks.append(cur)

for i, t in enumerate(tasks):
    json.dump({"task": i, "scenes": t},
              open(OUT / f"task_{i:03d}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print(f"작업 {len(tasks)}개, 씬 {sum(len(t) for t in tasks)}개 -> work/shrink_jp/")
print(f"줄일 글자 합계 약 {sum(math.ceil(r['over']/2)+4 for r in over)}자")
