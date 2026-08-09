#!/usr/bin/env python3
# batch_NNN_kr.json 의 번역을 skits/{slot}.json 의 kr 에 되쓴다 (빈 칸만 채움 기본).
#  사용: py work\skit_jp\_merge_kr.py [--force] [batch_001 ...]
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKITS = os.path.join(HERE, "skits")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--force", action="store_true", help="이미 채워진 kr도 덮어씀")
    args = ap.parse_args()

    names = args.names or [os.path.basename(f)[:-5]
                           for f in sorted(glob.glob(os.path.join(HERE, "batch_[0-9][0-9][0-9].json")))]

    # (slot,id) -> kr 수집
    kr_map = {}
    for n in names:
        dst = os.path.join(HERE, n + "_kr.json")
        if not os.path.exists(dst):
            continue
        for r in json.load(open(dst, encoding="utf-8")):
            kr = r.get("kr", "")
            if kr.strip():
                kr_map[(int(r["slot"]), str(r["id"]))] = kr

    # 슬롯별로 반영
    touched = collections_defaultdict()
    for (slot, _id) in kr_map:
        touched[slot] = True
    filled = 0
    for slot in touched:
        p = os.path.join(SKITS, f"{slot}.json")
        d = json.load(open(p, encoding="utf-8"))
        changed = False
        for l in d.get("lines", []):
            key = (slot, str(l["id"]))
            if key in kr_map and (args.force or not l.get("kr", "").strip()):
                if l.get("kr", "") != kr_map[key]:
                    l["kr"] = kr_map[key]
                    changed = True
                    filled += 1
        if changed:
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[OK] {len(touched)}개 슬롯, {filled}줄 반영")


def collections_defaultdict():
    import collections
    return collections.defaultdict(bool)


if __name__ == "__main__":
    main()
