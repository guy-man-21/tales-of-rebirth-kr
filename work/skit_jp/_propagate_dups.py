#!/usr/bin/env python3
# 축약된 대표 슬롯 kr 을 동일 텍스트였던 중복 슬롯들에 복사.
#  dup_map.json = {rep_slot: [dup_slot,...]}. rep 의 (id->kr) 를 dup 에 그대로 반영.
#  사용: py work\skit_jp\_propagate_dups.py <dup_map.json 경로>
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dup_map = json.load(open(sys.argv[1], encoding="utf-8"))

n = 0
for rep, dups in dup_map.items():
    rj = json.load(open(f"work/skit_jp/skits/{rep}.json", encoding="utf-8"))
    krmap = {l["id"]: l.get("kr", "") for l in rj["lines"]}
    for ds in dups:
        p = f"work/skit_jp/skits/{ds}.json"
        dj = json.load(open(p, encoding="utf-8"))
        ch = False
        for l in dj["lines"]:
            if l["id"] in krmap and l.get("kr", "") != krmap[l["id"]]:
                l["kr"] = krmap[l["id"]]; ch = True
        if ch:
            json.dump(dj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            n += 1
print(f"[OK] 중복 {n}개 슬롯에 대표 kr 전파")
