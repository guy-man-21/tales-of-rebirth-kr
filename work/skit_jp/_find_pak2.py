#!/usr/bin/env python3
# DAT 전 슬롯에서 PAK2(스킷) 파일 탐색.
#  PAK2: 앞 12B = u32 x3 오프셋. theirsce = file[off0:off1(또는 off2)]. THEIRSCE 매직이면 PAK2.
#  압축슬롯은 해제 후 검사. 결과: 스킷 슬롯 목록 + THEIRSCE 크기.
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib
from pythonlib.formats.rebirth import pak2 as pak2lib

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


def try_pak2(buf):
    if len(buf) < 12:
        return None
    try:
        rsce = pak2lib.get_theirsce_from_pak2(buf)
        if rsce[:8] == b"THEIRSCE":
            return len(rsce)
    except Exception:
        pass
    return None


skits = []
for s in range(len(ptrs) - 1):
    lo, hi = ptrs[s], ptrs[s + 1]
    if hi - lo < 12:
        continue
    blob = dat[lo:hi]
    comp = False
    buf = blob
    if comptolib.is_compressed(blob):
        try:
            buf = comptolib.decompress_data(blob)
            comp = True
        except Exception:
            buf = blob
    r = try_pak2(buf)
    if r:
        skits.append({"slot": s, "off": lo, "blob_len": hi - lo,
                      "compressed": comp, "rsce_len": r})

print(f"PAK2(스킷) 파일 {len(skits)}개")
for sk in skits[:80]:
    print(f"  슬롯 {sk['slot']:5d} @0x{sk['off']:X} blob {sk['blob_len']:7d} "
          f"{'comp' if sk['compressed'] else 'raw '} rsce {sk['rsce_len']}")
json.dump(skits, open("work/skit_jp/_skit_slots.json", "w"), ensure_ascii=False, indent=1)
print("-> work/skit_jp/_skit_slots.json")
