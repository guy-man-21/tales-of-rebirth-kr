#!/usr/bin/env python3
# eboot_work.json 의 title 카테고리 「」형 미번역 행을 배치로 묶는다.
#  각 행에 off/jp/avail. avail = 인코딩 바이트 예산(널 포함) — kr 인코딩 <= avail-1.
#  사용: py work\eboot_jp\_title_batches.py [--per 90]
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=90)
    args = ap.parse_args()
    rows = json.load(open(os.path.join(HERE, "eboot_work.json"), encoding="utf-8"))
    todo = [r for r in rows
            if r["cat"] == "title" and r["jp"].startswith("「") and not r.get("kr", "").strip()]
    batches = [todo[i:i + args.per] for i in range(0, len(todo), args.per)]
    for i, b in enumerate(batches, 1):
        lines = [{"off": r["off"], "avail": r["avail"], "jp": r["jp"]} for r in b]
        json.dump({"batch": i, "lines": lines},
                  open(os.path.join(HERE, f"tbatch_{i:03d}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"[OK] {len(batches)}개 배치, {len(todo)}행 (「」형 title 미번역)")


if __name__ == "__main__":
    main()
