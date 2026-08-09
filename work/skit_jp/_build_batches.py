#!/usr/bin/env python3
# 스킷 코퍼스(skits/*.json)의 미번역(kr 빈칸) 줄을 배치로 묶는다.
#  각 줄에 slot+id 를 실어 -> batch_NNN.json. 번역 후 _merge_kr.py 로 되돌림.
#  본편 work/mt 와 동일 컨셉의 스킷판.
#  사용: py work\skit_jp\_build_batches.py [--per 120]
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKITS = os.path.join(HERE, "skits")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=120, help="배치당 줄 수 상한")
    ap.add_argument("--only-empty", action="store_true", default=True)
    args = ap.parse_args()

    # 슬롯 오름차순으로 순회, 스킷(슬롯) 경계를 넘지 않게 묶되 per 초과 시 새 배치.
    slots = sorted(int(os.path.basename(f)[:-5]) for f in glob.glob(os.path.join(SKITS, "*.json")))

    batches = []
    cur = []
    for slot in slots:
        d = json.load(open(os.path.join(SKITS, f"{slot}.json"), encoding="utf-8"))
        todo = [l for l in d.get("lines", []) if not l.get("kr", "").strip()]
        if not todo:
            continue
        # 스킷 하나가 통째로 per 를 넘으면 그대로 한 배치(문맥 유지 우선)
        if cur and len(cur) + len(todo) > args.per:
            batches.append(cur)
            cur = []
        for l in todo:
            cur.append({"slot": slot, "id": str(l["id"]), "jp": l["jp"]})
    if cur:
        batches.append(cur)

    for i, b in enumerate(batches, 1):
        name = f"batch_{i:03d}.json"
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            json.dump({"batch": i, "lines": b}, f, ensure_ascii=False, indent=1)
    total = sum(len(b) for b in batches)
    print(f"[OK] {len(batches)}개 배치, {total}줄 (미번역만)")
    print(f"     batch_001.json ~ batch_{len(batches):03d}.json")


if __name__ == "__main__":
    main()
