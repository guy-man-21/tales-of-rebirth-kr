#!/usr/bin/env python3
# 컴팩트 한글 줄거리 블롭을 슬롯3969 '제자리'에 적용 (DAT 크기·구조 불변 — repack 불필요).
#  전제: _compact.py 재압축 <= 16608. 블롭 뒤 원본 footprint 잔여는 널.
#  사용: py work\synopsis_jp\_apply_inplace.py [--check]
import argparse
import os
import struct
import subprocess
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pythonlib.utils import comptolib

PTR = 0x126F90
SLOT = 3969
FOOT = 16608


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, "work/synopsis_jp/_compact.py",
                    "--out", "work/synopsis_jp/_compact_blob.bin"], env=env)
    blob = open("work/synopsis_jp/_compact_blob.bin", "rb").read()
    comp = comptolib.compress_data(blob, version=1)
    if comptolib.decompress_data(comp) != blob:
        print("[중단] roundtrip 불일치")
        return
    print(f"압축 {len(comp)}B / footprint {FOOT}B", "적합" if len(comp) <= FOOT else "초과!")
    if len(comp) > FOOT:
        print("[중단] 아직 초과 — 트림 더 필요")
        return

    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    eb = open("EBOOT_jp_new.BIN", "rb").read()
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > len(dat) * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    lo = p[SLOT] - 32
    if dat[lo] not in (1, 3):
        print(f"[중단] {hex(lo)} 블롭 시작 아님")
        return
    if args.check:
        print(f"[검사] 쓰기 위치 {hex(lo)}, {len(comp)}B + 널 {FOOT-len(comp)}B (크기불변)")
        return
    dat[lo:lo + len(comp)] = comp
    for q in range(lo + len(comp), lo + FOOT):
        dat[q] = 0
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    print(f"[OK] DAT_jp_final 슬롯{SLOT} 제자리 갱신 (크기불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
