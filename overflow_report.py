#!/usr/bin/env python3
# ============================================================
#  overflow_report.py -- 원본 블롭 자리에 안 들어가는 씬과 '몇 바이트 넘치는지'
#
#  DAT 레이아웃은 못 바꾼다(EBOOT 2차 오프셋 테이블이 절대위치를 참조).
#  따라서 각 씬의 THEIRSCE 는 원본 블롭 크기 S 안에 들어가야 한다. 예산 = S - 9.
#  넘치는 만큼 번역을 줄여야 한다. 한글 1자 = 2바이트.
#
#  사용: py overflow_report.py [--out overflow.json]
# ============================================================
import argparse
import json
import struct
import sys
from pathlib import Path

PYTHONLIB_PATH = r"D:\PythonLib"
PTR = 0x126F90
HDR = 9


def read_pointers(eboot, dat_size):
    ptrs, i = [], 0
    while True:
        v = struct.unpack_from("<I", eboot, PTR + i * 4)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size * 1.05):
            break
        ptrs.append(v)
        i += 1
        if i > 40000:
            break
    return ptrs


ap = argparse.ArgumentParser()
ap.add_argument("--out", default="overflow.json")
args = ap.parse_args()

sys.path.insert(0, PYTHONLIB_PATH)
sys.path.insert(0, ".")
from pythonlib.formats.rebirth.theirsce import Theirsce  # noqa: E402

from build_scene import inject_translation  # noqa: E402
from scpk_patch import find_container  # noqa: E402
from story_pipeline_bin import make_mini  # noqa: E402

mini_ex = make_mini("tbl_all.json")
mini_in = make_mini("tbl_full_kr.json")

dat = Path("DAT_cn.BIN").read_bytes()
ptrs = read_pointers(Path("EBOOT_DEC.BIN").read_bytes(), len(dat))
scenes = sorted(int(p.stem) for p in Path("translation").glob("*.json")
                if p.stem.isdigit())

rows = []
for sc in scenes:
    try:
        c = find_container(dat, ptrs, sc)
        t = c["theirsce_off"]
        csize = struct.unpack_from("<I", dat, t - 8)[0]
        block = dat[t:t + csize]
        S = c["blob_size"]

        mini_ex.id = 1
        xml_raw = f"work/{sc}.xml"
        Path(xml_raw).write_bytes(
            mini_ex.get_xml_from_theirsce(Theirsce(block), "Story"))
        data = json.load(open(f"translation/{sc}.json", encoding="utf-8"))
        inject_translation(xml_raw, f"work/{sc}_KR.xml", data.get("lines", []))

        mini_in.id = 1
        tt = mini_in.get_new_theirsce(Theirsce(block), Path(f"work/{sc}_KR.xml"))
        tt.seek(0)
        L = len(tt.read())
        budget = S - HDR
        rows.append({"scene": sc, "budget": budget, "need": L,
                     "over": L - budget})
    except Exception:
        continue

over = [r for r in rows if r["over"] > 0]
over.sort(key=lambda r: -r["over"])
tot = sum(r["over"] for r in over)
print(f"[결과] 검사 {len(rows)}씬 / 초과 {len(over)}씬 / 총 초과 {tot:,}B")
if over:
    med = sorted(r["over"] for r in over)[len(over) // 2]
    print(f"  초과 바이트 중앙값 {med}B (= 한글 약 {med // 2}자)")
    print(f"\n  {'씬':>6} {'예산':>8} {'필요':>8} {'초과':>7} {'줄일 글자수':>10}")
    for r in over[:25]:
        print(f"  {r['scene']:>6} {r['budget']:>8} {r['need']:>8} "
              f"{r['over']:>7} {-(-r['over'] // 2):>10}")
    if len(over) > 25:
        print(f"  ... 외 {len(over) - 25}개")

json.dump(over, open(args.out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n-> {args.out}")
