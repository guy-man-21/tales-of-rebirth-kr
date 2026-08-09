#!/usr/bin/env python3
# 스킷 본문(書いてるんだ)을 타깃으로 DAT 전 슬롯을 강건하게 스캔.
#  - ±미스얼라인 보정(lo-64..lo+8 에서 comptolib 헤더 탐색)
#  - PAK3(중첩) 언랩: 슬롯 해제 -> pak 서브파일 각각 해제
#  - FLD.BIN 도 comptolib 블록 순차 워크로 검색
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
    o = b""
    for c in s:
        if c in inv:
            o += bytes.fromhex(inv[c])
        elif ord(c) < 0x80:
            o += bytes([ord(c)])
    return o


TARGET = enc("書いてるんだ")
PAK2SIG = struct.pack("<I", 0x20)  # PAK2 offsets[0]=0x20


def dec_at(buf):
    """buf 가 comptolib 이면 해제, 아니면 None."""
    if len(buf) >= 9 and buf[0] in (1, 3):
        try:
            csz = struct.unpack_from("<I", buf, 1)[0]
            if 0 < csz <= len(buf):
                return comptolib.decompress_data(buf[:9 + csz])
        except Exception:
            pass
    return None


def unwrap_search(buf, depth=0):
    """buf 내부(및 PAK 서브파일)에서 TARGET/PAK2SIG 검색."""
    if TARGET in buf:
        return "TARGET"
    if depth >= 3:
        return None
    # PAK(0/1/3) 서브파일 시도
    if len(buf) >= 8:
        n = struct.unpack_from("<I", buf, 0)[0]
        if 0 < n < 4096 and (n + 1) * 4 <= len(buf):
            try:
                offs = list(struct.unpack_from("<%dI" % n, buf, 4))
                if all(offs[k] < offs[k + 1] for k in range(n - 1)) and offs[0] >= 4 + n * 4 and offs[-1] <= len(buf):
                    for a, b in zip(offs, offs[1:] + [len(buf)]):
                        sub = buf[a:b]
                        d = dec_at(sub) or sub
                        r = unwrap_search(d, depth + 1)
                        if r:
                            return f"pak/{r}"
            except Exception:
                pass
    return None


def main():
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

    print(f"DAT {len(ptrs)-1} 슬롯 강건 스캔", flush=True)
    hits = []
    for s in range(len(ptrs) - 1):
        lo, hi = ptrs[s], ptrs[s + 1]
        if hi - lo < 12:
            continue
        found = None
        # 미스얼라인 보정: lo-64..lo+8
        for delta in range(-64, 9):
            o = lo + delta
            if o < 0:
                continue
            d = dec_at(dat[o:hi + 64])
            if d is None:
                continue
            r = unwrap_search(d)
            if r:
                found = (delta, r, len(d))
                break
        # raw 도
        if not found and TARGET in dat[lo:hi]:
            found = (0, "raw", hi - lo)
        if found:
            hits.append({"slot": s, "off": lo, "info": found})
            print(f"  [HIT] 슬롯 {s} @0x{lo:X} {found}", flush=True)
        if s % 2000 == 0:
            print(f"  ...{s}", flush=True)

    print(f"DAT 완료. hits={len(hits)}", flush=True)

    # FLD.BIN 순차 comptolib 워크
    FLD = open(r"C:/Users/home/Desktop/프로그램/ppsspp_win/roms/torj/PSP_GAME/USRDIR/FLD.BIN", "rb").read()
    print(f"FLD.BIN {len(FLD)}B 순차 워크", flush=True)
    p = 0
    fld_hits = []
    steps = 0
    while p < len(FLD) - 9:
        t = FLD[p]
        if t in (1, 3):
            csz = struct.unpack_from("<I", FLD, p + 1)[0]
            if 0 < csz < len(FLD):
                try:
                    d = comptolib.decompress_data(FLD[p:p + 9 + csz])
                    if TARGET in d or PAK2SIG == d[:4]:
                        fld_hits.append(p)
                        print(f"  [FLD HIT] @0x{p:X}", flush=True)
                    p += 9 + csz
                    steps += 1
                    if steps % 20000 == 0:
                        print(f"  FLD ...0x{p:X}", flush=True)
                    continue
                except Exception:
                    pass
        p += 1
    print(f"FLD 완료. hits={len(fld_hits)}", flush=True)
    json.dump({"dat": hits, "fld": fld_hits}, open("work/skit_jp/_robust.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
