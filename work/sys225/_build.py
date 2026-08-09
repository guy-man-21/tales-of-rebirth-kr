#!/usr/bin/env python3
# 비SCPK 씬 225/226/227 (파티편성/notice/판매 등 시스템 THEIRSCE) 한글 제자리 패치.
#  구조: [데이터][THEIRSCE @블록+~0x12fc0][후속데이터]. THEIRSCE 는 비압축.
#  한글 재구성 THEIRSCE 가 원본보다 작음 -> 원본 THEIRSCE 길이까지 널패딩(후속데이터 위치 불변).
#  src=DAT.BIN(클린) 추출/주입, dst=DAT_jp_final 제자리 쓰기.
#  사용: py work\sys225\_build.py [--dat DAT_jp_final.BIN] [--check]
import argparse
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from story_pipeline_bin import make_mini
from pythonlib.formats.rebirth.theirsce import Theirsce
from build_scene import inject_translation
from pathlib import Path

PTR = 0x126F90
SCENES = [225, 226, 227]
TMP = "work/sys225"


def read_ptrs(eb, dsize):
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > dsize * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    src = open("DAT.BIN", "rb").read()
    src_ptrs = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    dat = bytearray(open(args.dat, "rb").read())
    dst_ptrs = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))

    ok = over = err = 0
    for SC in SCENES:
        so, se = src_ptrs[SC], src_ptrs[SC + 1]
        sblk = src[so:se]
        t = sblk.find(b"THEIRSCE")
        if t < 0:
            err += 1
            print(f"  씬{SC}: THEIRSCE 없음")
            continue
        rsce = sblk[t:]
        mex = make_mini("tbl_all.json"); mex.id = 1
        mn = make_mini("tbl_full_kr.json"); mn.id = 1
        # 원본 THEIRSCE 길이
        xmlj = mex.get_xml_from_theirsce(Theirsce(rsce), "Story")
        Path(f"{TMP}/_o.xml").write_bytes(xmlj if isinstance(xmlj, (bytes, bytearray)) else xmlj.encode())
        mo = make_mini("tbl_all.json"); mo.id = 1
        ont = mo.get_new_theirsce(Theirsce(rsce), Path(f"{TMP}/_o.xml")); ont.seek(0)
        orig_len = len(ont.read())
        # 한글 주입
        tr = json.load(open(f"translation/{SC}.json", encoding="utf-8"))
        lines = [l for l in tr["lines"] if (l.get("kr") or "").strip()]
        mex.id = 1
        Path(f"{TMP}/_j.xml").write_bytes(xmlj if isinstance(xmlj, (bytes, bytearray)) else xmlj.encode())
        inject_translation(f"{TMP}/_j.xml", f"{TMP}/_k.xml", lines, field="EnglishText")
        mn.id = 1
        nt = mn.get_new_theirsce(Theirsce(rsce), Path(f"{TMP}/_k.xml")); nt.seek(0)
        newr = nt.read()
        if len(newr) > orig_len:
            over += 1
            print(f"  씬{SC}: 초과 {len(newr)}>{orig_len} (+{len(newr)-orig_len})")
            continue
        # dst 위치: dst 블록에서 THEIRSCE 오프셋 (동일 상대위치라 가정, 확인)
        do = dst_ptrs[SC]
        dblk_t = dat.find(b"THEIRSCE", do, dst_ptrs[SC + 1])
        if dblk_t < 0:
            err += 1
            print(f"  씬{SC}: dst THEIRSCE 없음")
            continue
        if not args.check:
            dat[dblk_t:dblk_t + len(newr)] = newr
            for q in range(dblk_t + len(newr), dblk_t + orig_len):
                dat[q] = 0
        ok += 1
        print(f"  씬{SC}: OK kr줄 {len(lines)} / THEIRSCE {len(newr)}<={orig_len} / dst@{hex(dblk_t)}")

    print(f"[{'검사' if args.check else '적용'}] OK {ok} / 초과 {over} / 에러 {err}")
    if not args.check and ok and over == 0 and err == 0:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 씬225/226/227 갱신 (크기불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
