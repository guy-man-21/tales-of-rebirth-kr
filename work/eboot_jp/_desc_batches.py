#!/usr/bin/env python3
# desc_work.json 미번역 행을 배치로. 사용: py work\eboot_jp\_desc_batches.py [--per 70]
import argparse, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument("--per", type=int, default=70); a = ap.parse_args()
rows = json.load(open(os.path.join(HERE, "desc_work.json"), encoding="utf-8"))
todo = [r for r in rows if not r.get("kr", "").strip()]
b = [todo[i:i+a.per] for i in range(0, len(todo), a.per)]
for i, x in enumerate(b, 1):
    json.dump({"batch": i, "lines": [{"off": r["off"], "avail": r["avail"], "jp": r["jp"]} for r in x]},
              open(os.path.join(HERE, f"dbatch_{i:03d}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[OK] {len(b)}개 배치, {len(todo)}행")
