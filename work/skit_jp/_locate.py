#!/usr/bin/env python3
# 스킷 컨테이너 탐색: DAT 전 슬롯을 해제하며 스킷 원문(encoded)을 검색.
#  각 슬롯: SCPK면 THEIRSCE 해제 / comptolib면 해제 / 아니면 raw. 그 안에서 패턴 검색.
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

Tall = json.load(open("tbl_all.json", encoding="utf-8"))
Tall = Tall.get("TBL", Tall)
inv = {}
for k, v in Tall.items():
    inv.setdefault(v, k)


def enc(s):
    out = bytearray()
    for c in s:
        if c in inv:
            out += bytes.fromhex(inv[c])
        elif ord(c) < 0x80:
            out.append(ord(c))
        else:
            return None
    return bytes(out)


PAT = [enc("バトルブック"), enc("クレアさん家"), enc("書いてる")]
PAT = [p for p in PAT if p]

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
print(f"슬롯 {len(ptrs)-1}개 스캔 시작", flush=True)


def try_decompress(blob):
    outs = []
    if blob[:4] == b"SCPK":
        return outs  # SCPK 은 아래서 별도
    b0 = blob[0] if blob else 0xFF
    if b0 in (0, 1, 3) and len(blob) >= 9:
        csz = struct.unpack_from("<I", blob, 1)[0]
        if 0 < csz <= len(blob):
            try:
                outs.append(comptolib.decompress_data(blob[:9 + csz]))
            except Exception:
                pass
    return outs


hits = []
for s in range(len(ptrs) - 1):
    lo, hi = ptrs[s], ptrs[s + 1]
    if hi <= lo or hi - lo < 9:
        continue
    blob = dat[lo:hi]
    bufs = [blob]  # raw 도 검색
    # SCPK 내부 THEIRSCE
    p = blob.find(b"SCPK")
    if p >= 0:
        try:
            nf = struct.unpack_from("<I", blob, p + 8)[0]
            if 0 < nf < 100:
                sizes = [struct.unpack_from("<I", blob, p + 16 + 4 * k)[0] for k in range(nf)]
                cur = p + 16 + 4 * nf
                for sz in sizes:
                    sub = blob[cur:cur + sz]
                    if sub[:1] and sub[0] in (0, 1, 3) and len(sub) >= 9:
                        csz = struct.unpack_from("<I", sub, 1)[0]
                        if 0 < csz <= len(sub):
                            try:
                                bufs.append(comptolib.decompress_data(sub[:9 + csz]))
                            except Exception:
                                pass
                    cur += sz
        except Exception:
            pass
    bufs += try_decompress(blob)
    for buf in bufs:
        for pat in PAT:
            if pat in buf:
                hits.append(s)
                print(f"  [HIT] 슬롯 {s} @0x{lo:X} (crc len {hi-lo})", flush=True)
                break
        else:
            continue
        break
    if s % 2000 == 0:
        print(f"  ...{s}/{len(ptrs)-1}", flush=True)

print(f"완료. 히트 슬롯: {hits}", flush=True)
json.dump(hits, open("work/skit_jp/_hits.json", "w"), ensure_ascii=False)
