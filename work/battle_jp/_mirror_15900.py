#!/usr/bin/env python3
# 슬롯15900 = 슬롯2 스트림1(ELF 591,304B 해제본)의 '비압축 사본' (오프셋 -56 시프트, 2026-07-18 실측).
#  배틀북 열람 화면(전투 중 조작 목록 등)이 이 슬롯을 읽음 -> 슬롯2 번역을 그대로 미러링.
#  방법: 원본 슬롯2 해제(d0) vs 현재 최종본 슬롯2 해제(dn)의 diff 를 15900 raw 에 복사.
#  in-place (크기 불변). 사용: py work\battle_jp\_mirror_15900.py [--check]
import os
import struct
import sys

os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

PTR = 0x126F90
SHIFT = 56          # raw15900[i] == d0[i+56]


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
    check = "--check" in sys.argv
    jp = open("DAT.BIN", "rb").read()
    pj = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(jp))
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    pn = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))

    # 원본/패치본 슬롯2 해제
    b0 = jp[pj[2]:pj[3]]
    c0 = struct.unpack_from("<I", b0, 1)[0]
    d0 = comptolib.decompress_data(b0[:9 + c0])
    b1 = bytes(dat[pn[2]:pn[3]])
    c1 = struct.unpack_from("<I", b1, 1)[0]
    dn = comptolib.decompress_data(b1[:9 + c1])
    assert len(d0) == len(dn)

    lo, hi = pn[15900], pn[15901]
    L = hi - lo
    applied = mismatch = 0
    for i in range(L):
        s = i + SHIFT
        if s >= len(d0):
            break
        if d0[s] != dn[s]:                      # 슬롯2에서 번역으로 바뀐 바이트
            if dat[lo + i] == d0[s]:            # 15900 쪽이 원본과 일치할 때만
                if not check:
                    dat[lo + i] = dn[s]
                applied += 1
            else:
                mismatch += 1
    print(f"[{'검사' if check else '적용'}] 미러 {applied}바이트 / 불일치 {mismatch}")
    if not check and applied:
        open("DAT_jp_final.BIN", "wb").write(bytes(dat))
        print(f"[OK] 슬롯15900 미러링 완료 (크기불변)")


if __name__ == "__main__":
    main()
