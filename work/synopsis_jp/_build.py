#!/usr/bin/env python3
# synopsis_work.json(kr) -> 슬롯3969 해제데이터 제자리 교체 -> 재압축 -> DAT_jp_final 패치.
#  각 조각: kr 인코딩(회수2B/ASCII1B/<XX>1B) <= 원문 blen. 널종료+원문길이까지 널패딩.
#  offset table 불변(길이 이내라 후속 조각 오프셋 유지). 재압축이 원본 footprint 이내면 in-place.
#  사용: py work\synopsis_jp\_build.py [--check]
import argparse
import json
import os
import re
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pythonlib.utils import comptolib

Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
PTR = 0x126F90
SLOT = 3969
TAG = re.compile(r"<([0-9A-Fa-f]{2})>")


def enc(kr):
    out = bytearray()
    i = 0
    while i < len(kr):
        m = TAG.match(kr, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        c = kr[i]
        if c in inv:
            out += struct.pack(">H", inv[c])
            i += 1
        elif ord(c) < 0x80:
            out.append(ord(c))
            i += 1
        else:
            return None, c
    return bytes(out), None


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


def find_comp(buf, lo):
    for dl in range(-64, 9):
        o = lo + dl
        if o < 0 or o + 9 > len(buf) or buf[o] not in (1, 3):
            continue
        try:
            csz = struct.unpack_from("<I", buf, o + 1)[0]
            if csz <= 0 or csz > 5_000_000:
                continue
            d = comptolib.decompress_data(bytes(buf[o:o + 9 + csz]))
            return o, 9 + csz, d, buf[o]
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    args = ap.parse_args()

    src = open("DAT.BIN", "rb").read()
    src_ptrs = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    rs = find_comp(src, src_ptrs[SLOT])
    o_src, _, d0, ctype = rs
    d = bytearray(d0)

    rows = json.load(open("work/synopsis_jp/synopsis_work.json", encoding="utf-8"))
    ok = skip = over = err = 0
    probs = []
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr:
            skip += 1
            continue
        e, bad = enc(kr)
        if e is None:
            err += 1
            probs.append((r["off"], f"인코딩불가 {bad!r}", kr))
            continue
        if len(e) > r["blen"]:
            over += 1
            probs.append((r["off"], f"초과 {len(e)}>{r['blen']}", kr))
            continue
        off = r["off"]
        d[off:off + len(e)] = e
        for p in range(off + len(e), off + r["blen"]):
            d[p] = 0
        ok += 1

    # 재압축
    comp = comptolib.compress_data(bytes(d), version=ctype)
    # 최종본에서 쓰기 위치/footprint
    dat = bytearray(open(args.dat, "rb").read())
    dat_ptrs = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    rd = find_comp(dat, dat_ptrs[SLOT])
    o_dst, orig_clen, _, _ = rd

    print(f"[{'검사' if args.check else '빌드'}] 조각 OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
    print(f"  재압축 {len(comp)}B / 원본footprint {orig_clen}B "
          f"({'적합' if len(comp) <= orig_clen else '초과 +%d' % (len(comp) - orig_clen)})")
    for off, msg, kr in probs[:30]:
        print(f"  +{off:#x}: {msg}  kr={kr!r}")

    if not args.check and over == 0 and err == 0 and len(comp) <= orig_clen:
        dat[o_dst:o_dst + len(comp)] = comp
        for p in range(o_dst + len(comp), o_dst + orig_clen):
            dat[p] = 0
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯3969 갱신 (크기불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
