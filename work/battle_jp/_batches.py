#!/usr/bin/env python3
# slot2_work.json 의 미번역 항목을 번역 배치로 분할
import json
import os

os.chdir(r"D:\clean_project")
rows = json.load(open("work/battle_jp/slot2_work.json", encoding="utf-8"))
todo = [r for r in rows if not (r.get("kr") or "").strip()]
print(f"미번역 {len(todo)}개")

PER = 70
n = 0
for i in range(0, len(todo), PER):
    batch = todo[i:i+PER]
    json.dump(batch, open(f"work/battle_jp/task_{n:03d}.json", "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  task_{n:03d}.json: {len(batch)}개")
    n += 1
