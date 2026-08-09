#!/usr/bin/env python3
# synopsis_work.json 미번역 조각을 '연속' 배치로. 사용: py work\synopsis_jp\_batches.py [--per 85]
import argparse, json, os
HERE=os.path.dirname(os.path.abspath(__file__))
ap=argparse.ArgumentParser(); ap.add_argument("--per",type=int,default=85); a=ap.parse_args()
rows=json.load(open(os.path.join(HERE,"synopsis_work.json"),encoding="utf-8"))
# 순서 유지, 미번역만
todo=[r for r in rows if not r.get("kr","").strip()]
b=[todo[i:i+a.per] for i in range(0,len(todo),a.per)]
for i,x in enumerate(b,1):
    json.dump({"batch":i,"lines":[{"off":r["off"],"blen":r["blen"],"jp":r["jp"]} for r in x]},
              open(os.path.join(HERE,f"sbatch_{i:03d}.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"[OK] {len(b)}개 배치, {len(todo)}조각")
