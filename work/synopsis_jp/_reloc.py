#!/usr/bin/env python3
# 슬롯3969(줄거리) 한글 블롭을 DAT 끝에 재배치 + ptr[3969] 갱신.
#  ★성장분을 2048(섹터) 배수로 패딩 (정렬 안 지키면 부팅 실패 — 실증됨).
#  슬롯3969는 2차테이블(226~3212) 밖이라 2차테이블 갱신 불필요.
#  사용: py work\synopsis_jp\_reloc.py [--check]
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
SECTOR = 2048


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
    args = ap.parse_args()

    # 1) 클린 src에서 해제 + 한글 주입
    src = open("DAT.BIN", "rb").read()
    src_ptrs = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    o_src, _, d0, ctype = find_comp(src, src_ptrs[SLOT])
    d = bytearray(d0)
    rows = json.load(open("work/synopsis_jp/synopsis_work.json", encoding="utf-8"))
    over = err = ok = 0
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr:
            continue
        e, bad = enc(kr)
        if e is None:
            err += 1
            print(f"  인코딩불가 @{r['off']:#x} {bad!r}")
            continue
        if len(e) > r["blen"]:
            over += 1
            print(f"  초과 @{r['off']:#x} {len(e)}>{r['blen']}")
            continue
        off = r["off"]
        d[off:off + len(e)] = e
        for p in range(off + len(e), off + r["blen"]):
            d[p] = 0
        ok += 1
    if over or err:
        print(f"[중단] 초과 {over} / 에러 {err} — 먼저 해결")
        return

    comp = comptolib.compress_data(bytes(d), version=ctype)
    print(f"[한글블롭] 조각 {ok}개, 재압축 {len(comp)}B")

    # 2) DAT 끝에 append + 2048 배수 패딩
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    eb = bytearray(open("EBOOT_jp_new.BIN", "rb").read())
    old_size = len(dat)
    new_blob_start = old_size
    grow = len(comp)
    grow_padded = ((grow + SECTOR - 1) // SECTOR) * SECTOR   # 성장분 2048 배수
    new_size = old_size + grow_padded
    old_ptr = struct.unpack_from("<I", eb, PTR + SLOT * 4)[0]
    new_ptr = new_blob_start + 32   # 원본 오프셋 퀴크(-32) 복제

    print(f"  DAT {old_size} -> {new_size} (성장 {grow_padded} = 2048x{grow_padded//SECTOR})")
    print(f"  ptr[{SLOT}] {old_ptr:#x} -> {new_ptr:#x}")
    print(f"  성장분 2048정렬: {grow_padded % SECTOR == 0}")

    if args.check:
        return

    dat += comp
    dat += b"\x00" * (grow_padded - grow)
    struct.pack_into("<I", eb, PTR + SLOT * 4, new_ptr)
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    open("EBOOT_jp_new.BIN", "wb").write(bytes(eb))
    print(f"[OK] 재배치 완료. DAT {len(dat)}B (delta from 983603328 = "
          f"{len(dat) - 983603328}, 2048정렬 {(len(dat) - 983603328) % SECTOR == 0})")


if __name__ == "__main__":
    main()
