#!/usr/bin/env python3
# eboot_work.json 의 title 카테고리 비「형 미번역 '실제 콘텐츠'를 배치로 묶는다.
#  (배틀북/줄거리/설정설명/요리/상점/지형/지역/몬스터명 등. 아이템·배틀help 구간 제외.)
#  안전필터: 가나 포함 OR 3개+ 밀집클러스터(gap<=24). 노이즈 한자는 에이전트가 추가로 스킵.
#  사용: py work\eboot_jp\_content_batches.py [--per 80]
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
# 이미 다른 파이프라인이 번역한 구간 (제외)
EXCLUDE = [(0xFDBF0, 0x106500), (0x105720, 0x105F00), (0x10FEB4, 0x10FFA0)]


def excluded(off):
    return any(lo <= off < hi for lo, hi in EXCLUDE)


def haskana(s):
    return any("぀" <= c <= "ゟ" or "゠" <= c <= "ヺ" for c in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=80)
    args = ap.parse_args()
    rows = json.load(open(os.path.join(HERE, "eboot_work.json"), encoding="utf-8"))
    non = sorted([r for r in rows
                  if r["cat"] == "title" and not r["jp"].startswith("「")
                  and not r.get("kr", "").strip() and len(r["jp"]) >= 2
                  and not excluded(r["off"])],
                 key=lambda r: r["off"])
    # 밀집 판정
    keep = []
    for i, r in enumerate(non):
        near = 0
        if i > 0 and r["off"] - non[i - 1]["off"] <= 24:
            near += 1
        if i + 1 < len(non) and non[i + 1]["off"] - r["off"] <= 24:
            near += 1
        if haskana(r["jp"]) or near >= 1:
            keep.append(r)
    batches = [keep[i:i + args.per] for i in range(0, len(keep), args.per)]
    for i, b in enumerate(batches, 1):
        lines = [{"off": r["off"], "avail": r["avail"], "jp": r["jp"]} for r in b]
        json.dump({"batch": i, "lines": lines},
                  open(os.path.join(HERE, f"cbatch_{i:03d}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"[OK] {len(batches)}개 배치, {len(keep)}행 (실제 콘텐츠 후보, 노이즈 최소)")


if __name__ == "__main__":
    main()
