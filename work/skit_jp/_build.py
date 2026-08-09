#!/usr/bin/env python3
# 스킷 코퍼스(skits/*.json, kr 채움) -> DAT_jp_final 슬롯 in-place 빌드.
#  각 스킷: THEIRSCE 재조립 -> create_pak2 -> 재압축. 원본 압축footprint 이내면 in-place.
#  초과분은 리포트(추후 repack). build_all_jp(씬)의 PAK2 판.
#  사용: py work\skit_jp\_build.py [--dat DAT_jp_final.BIN] [--check]
import argparse
import glob
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pythonlib.utils import comptolib
from pythonlib.formats.rebirth import pak2 as pak2lib
from pythonlib.formats.rebirth.theirsce import Theirsce
from story_pipeline_bin import make_mini
from build_scene import inject_translation
from lxml import etree
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    def read_ptrs(eb_bytes, dsize):
        p = []
        j = 0
        while True:
            v = struct.unpack_from("<I", eb_bytes, PTR + j * 4)[0]
            if j > 0 and (v < p[-1] or v > dsize * 1.05):
                break
            p.append(v)
            j += 1
            if j > 40000:
                break
        return p

    PTR = 0x126F90
    # src = 원본(깨끗한 스킷 PAK2 소스), dst = 최종본(쓰기 대상)
    src = open("DAT.BIN", "rb").read()
    src_ptrs = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    dat = bytearray(open(args.dat, "rb").read())
    ptrs = read_ptrs(open(args.eboot, "rb").read(), len(dat))

    def find_pak(buf, lo):
        for delta in range(-64, 9):
            o = lo + delta
            if o < 0 or o + 9 > len(buf) or buf[o] not in (1, 3):
                continue
            try:
                csz = struct.unpack_from("<I", buf, o + 1)[0]
                d = comptolib.decompress_data(bytes(buf[o:o + 9 + csz]))
                if d[:4] == struct.pack("<I", 0x20) and b"THEIRSCE" in d:
                    return o, 9 + csz, d, buf[o]
            except Exception:
                continue
        return None

    mex = make_mini("tbl_all.json")
    mex.id = 1
    min_ = make_mini("tbl_full_kr.json")
    min_.id = 1

    tmp = "work/skit_jp/_bx.xml"
    tmpk = "work/skit_jp/_bxKR.xml"
    ok = skip = over = err = 0
    over_list = []
    for f in sorted(glob.glob("work/skit_jp/skits/*.json"),
                    key=lambda p: int(os.path.basename(p)[:-5])):
        js = json.load(open(f, encoding="utf-8"))
        lines = [l for l in js["lines"] if (l.get("kr") or "").strip()]
        if not lines:
            skip += 1
            continue
        slot = js["slot"]
        # src(원본)에서 스킷 PAK2 읽기, dst(최종본)에서 쓸 위치 찾기
        rs = find_pak(src, src_ptrs[slot])
        rd = find_pak(dat, ptrs[slot])
        if rs is None or rd is None:
            err += 1
            over_list.append((slot, "압축시작 못찾음"))
            continue
        s_start, s_len, pak, ctype = rs   # 원본 PAK2 (깨끗)
        start, cur_len, _, _ = rd         # 최종본 쓰기 위치
        # ★재빌드 함정 수정(2026-07-25): 현재 블롭 길이(cur_len)는 이전 빌드의 압축 결과라
        #   원본 footprint 보다 작을 수 있음. 예산 = 원본 footprint (같은 위치 in-place 전제).
        srel = s_start - src_ptrs[slot]
        drel = start - ptrs[slot]
        orig_len = max(s_len, cur_len) if srel == drel else cur_len
        try:
            data = pak2lib.get_data(pak)
            rsce = data.chunks.theirsce
            mex.id = 1
            Path(tmp).write_bytes(mex.get_xml_from_theirsce(Theirsce(rsce), "Story"))
            inject_translation(tmp, tmpk, lines, field="EnglishText")
            min_.id = 1
            nt = min_.get_new_theirsce(Theirsce(rsce), Path(tmpk))
            nt.seek(0)
            data.chunks.theirsce = nt.read()
            new_pak = pak2lib.create_pak2(data)
            comp = comptolib.compress_data(new_pak, version=ctype)
        except Exception as e:
            err += 1
            over_list.append((slot, f"빌드오류 {e!r}"[:60]))
            continue
        if len(comp) > orig_len:
            over += 1
            over_list.append((slot, f"초과 {len(comp)}>{orig_len} (+{len(comp)-orig_len})"))
            continue
        if not args.check:
            dat[start:start + len(comp)] = comp
            for p in range(start + len(comp), start + orig_len):
                dat[p] = 0
        ok += 1

    print(f"[{'검사' if args.check else '빌드'}] OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
    for slot, msg in over_list:
        print(f"  슬롯 {slot}: {msg}")
    if not args.check and ok:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 스킷 {ok}개 in-place (크기불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
