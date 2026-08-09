#!/usr/bin/env python3
# ============================================================
#  verify_dat.py -- 빌드된 DAT/EBOOT 를 '새 포인터로' 다시 읽어 검증
#
#  빌드 결과를 그대로 신뢰하지 않고, 게임이 하는 것과 같은 순서로 읽는다:
#    새 EBOOT 포인터 -> 새 DAT 슬롯 -> SCPK 컨테이너 -> THEIRSCE -> 문자열 디코드
#  한국어가 나오면 인코딩/컨테이너/포인터가 모두 맞는 것이다.
#
#  사용: py verify_dat.py [--scenes 4246,4247] [--sample 5]
# ============================================================
import argparse
import random
import re
import struct
import sys
from pathlib import Path

PYTHONLIB_PATH = r"D:\PythonLib"
PTR = 0x126F90
TAG = re.compile(r"<[^>]+>")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default="DAT_cn_new.BIN")
    ap.add_argument("--eboot", default="EBOOT_cn_new.BIN")
    ap.add_argument("--tbl", default="tbl_full_kr.json")
    ap.add_argument("--scenes", default="")
    ap.add_argument("--sample", type=int, default=8)
    args = ap.parse_args()

    sys.path.insert(0, PYTHONLIB_PATH)
    sys.path.insert(0, ".")
    from lxml import etree
    from pythonlib.formats.rebirth.theirsce import Theirsce

    from scpk_patch import find_container
    from story_pipeline_bin import make_mini

    mini = make_mini(args.tbl)   # 한글 코드테이블로 디코드
    dat = Path(args.dat).read_bytes()
    eboot = Path(args.eboot).read_bytes()
    ptrs = read_pointers(eboot, len(dat))
    print(f"[i] {args.dat} {len(dat)}B, 포인터 {len(ptrs)}개")

    built = sorted(int(p.stem.split("_")[0]) for p in Path("build").glob("*_kr.bin"))
    if args.scenes:
        scenes = [int(s) for s in args.scenes.split(",") if s.strip()]
    else:
        random.seed(7)
        scenes = sorted(random.sample(built, min(args.sample, len(built))))

    ok = bad = 0
    for sc in scenes:
        try:
            c = find_container(dat, ptrs, sc)
            t = c["theirsce_off"]
            csize = struct.unpack_from("<I", dat, t - 8)[0]
            mini.id = 1
            xml = mini.get_xml_from_theirsce(Theirsce(dat[t:t + csize]), "Story")
            root = etree.fromstring(xml)
            texts = [e.findtext("JapaneseText") or ""
                     for e in root.findall(".//Strings//Entry")]
            texts = [TAG.sub("", x).strip() for x in texts]
            texts = [x for x in texts if x]
            kr = sum(1 for x in texts if any("가" <= ch <= "힣" for ch in x))
            mark = "[OK]" if kr else "[!] 한글 없음"
            if kr:
                ok += 1
            else:
                bad += 1
            print(f"  {mark} 씬 {sc}: 문자열 {len(texts)}개 중 한글 {kr}개")
            for x in texts[:2]:
                print(f"        {x[:52]!r}")
        except Exception as e:
            bad += 1
            print(f"  [X] 씬 {sc}: {type(e).__name__}: {e}")

    print(f"\n검증: 한글 확인 {ok}씬 / 문제 {bad}씬")


if __name__ == "__main__":
    main()
