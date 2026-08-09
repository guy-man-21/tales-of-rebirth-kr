#!/usr/bin/env python3
# DAT 전 슬롯에서 anp3 엔트리 열거 + 타이틀 팔레트(f7f2d3 램프) 보유 여부.
#  목적: 술즈 타이틀 이미지의 다른 사본/유사본(재압축본 포함)이 있는지 확인.
#  ★엔트리 사이에 비패딩 필러가 있어, 다음 헤더를 전방 탐색해야 함(실측).
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"C:\Users\jh-nb\Documents\project\PythonLib")
from pythonlib.utils import comptolib

dat = open("DAT.BIN", "rb").read()
eb = open("ULJS00132_EBOOT.BIN", "rb").read()
PTR = 0x126F90
ptrs = []
i = 0
while True:
    v = struct.unpack_from("<I", eb, PTR + i * 4)[0]
    if i > 0 and (v < ptrs[-1] or v > len(dat) * 1.05):
        break
    ptrs.append(v)
    i += 1
    if i > 40000:
        break

RAMP = bytes.fromhex("f7f2d3")


def next_entry(q, hi):
    """q 이후 첫 유효 comptolib 엔트리 (o, csize, data). 없으면 None."""
    for step in range(0, 512):
        o = q + step
        if o + 9 >= hi or dat[o] not in (1, 3):
            continue
        c = struct.unpack_from("<I", dat, o + 1)[0]
        dz = struct.unpack_from("<I", dat, o + 5)[0]
        if not (16 < c <= hi - o + 4096) or not (0 < dz < 64 * 1024 * 1024):
            continue
        try:
            dd = comptolib.decompress_data(dat[o:o + 9 + c])
        except Exception:
            continue
        if len(dd) == dz:
            return o, c, dd
    return None


found = []
for s in range(len(ptrs) - 1):
    lo, hi = ptrs[s], ptrs[s + 1]
    if hi - lo < 64:
        continue
    q = lo
    for _ in range(64):
        r = next_entry(q, hi)
        if r is None:
            break
        o, c, d = r
        if d[:4] == b"anp3" and RAMP in d:
            data_off = struct.unpack_from("<I", d, 8)[0]
            pal_off = struct.unpack_from("<I", d, 12)[0]
            found.append({"slot": s, "off": o, "csz": c, "dsz": len(d),
                          "data_off": data_off, "pal_off": pal_off})
            print("  [HIT] 슬롯 %d @0x%X csz=%d dsz=%d data=0x%X pal=0x%X"
                  % (s, o, c, len(d), data_off, pal_off), flush=True)
        q = o + 9 + c
    if s % 2000 == 0:
        print("  ...%d (누적 %d)" % (s, len(found)), flush=True)

print("완료: 타이틀 팔레트 보유 anp3 %d개" % len(found), flush=True)
json.dump(found, open("work/title_img/_anp3_title_like.json", "w"), indent=1)
