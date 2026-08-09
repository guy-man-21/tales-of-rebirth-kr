#!/usr/bin/env python3
# 시스템 배치 번역 정규화:
#  (1) 같은 원문(jp)은 같은 번역(kr)으로 통일. 배치/에이전트마다 갈린 표기를
#      가장 많이 쓰인(최빈) kr 로 맞춘다. (아레나 반복 문구: 관/저택, HIT/히트,
#      전각/반각 숫자 등 자동 통일)
#  (2) 용어 고정(부분 치환): 바이러스->바이라스, 알반 산맥->아르반 산맥.
#  work/sys/batch_*_kr.json 을 제자리 수정. dry-run 후 --apply.
import json, glob, os, sys, re
from collections import Counter, defaultdict

MTDIR = r"D:\clean_project\work\sys"
apply = "--apply" in sys.argv

# 투표 전 사전 통일: 전각 !? 와 전각 숫자 -> 반각 (CLAUDE.md: 반각 !?)
_FW = "！？０１２３４５６７８９"
_HW = "!?0123456789"
_TR = str.maketrans(_FW, _HW)
def pre_norm(s):
    return s.translate(_TR)

# jp(원문) 로드: batch_NNN.json
jp_of = {}   # (scene,id) -> jp
for f in sorted(glob.glob(os.path.join(MTDIR, "batch_[0-9][0-9][0-9].json"))):
    for l in json.load(open(f, encoding="utf-8"))["lines"]:
        jp_of[(int(l["scene"]), str(l["id"]))] = l["jp"]

# kr 수집: jp -> Counter(kr)  (빈 kr 제외 = 디버그 블랭크는 통일 대상 아님)
jp_krs = defaultdict(Counter)
recs = []  # (file, list-of-rows)
for f in sorted(glob.glob(os.path.join(MTDIR, "batch_*_kr.json"))):
    data = json.load(open(f, encoding="utf-8"))
    recs.append((f, data))
    for r in data:
        jp = jp_of.get((int(r["scene"]), str(r["id"])), None)
        kr = r.get("kr", "")
        if jp is not None and kr.strip():
            jp_krs[jp][pre_norm(kr)] += 1

# 각 jp 의 canonical kr = 최빈(동률이면 짧은 것)
canon = {}
for jp, c in jp_krs.items():
    if len(c) <= 1:
        continue
    best = sorted(c.items(), key=lambda kv: (-kv[1], len(kv[0])))[0][0]
    canon[jp] = best

TERM_SUBS = [("바이러스", "바이라스"), ("알반 산맥", "아르반 산맥")]

n_uni = n_term = 0
for f, data in recs:
    dirty = False
    for r in data:
        jp = jp_of.get((int(r["scene"]), str(r["id"])), None)
        kr = r.get("kr", "")
        if not kr.strip():
            continue
        new = pre_norm(kr)
        if new != kr:
            n_uni += 0  # pre_norm 자체 변경도 반영
        if jp in canon and new != canon[jp]:
            new = canon[jp]; n_uni += 1
        for a, b in TERM_SUBS:
            if a in new:
                new = new.replace(a, b); n_term += 1
        if new != kr:
            r["kr"] = new; dirty = True
    if apply and dirty:
        json.dump(data, open(f, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

# 통일 대상 리포트
multi = {jp: c for jp, c in jp_krs.items() if len(c) > 1}
print(f"[{'적용' if apply else 'DRY-RUN'}] 같은원문 다른번역 {len(multi)}종 -> canonical 통일 {n_uni}줄, 용어치환 {n_term}건")
for jp, c in list(sorted(multi.items(), key=lambda kv: -sum(kv[1].values())))[:12]:
    print(f"  jp={jp[:30]!r} -> {dict(c)} => {canon.get(jp,'')[:25]!r}")
