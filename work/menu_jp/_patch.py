#!/usr/bin/env python3
# menu_work.json(kr 채움)을 DAT 슬롯3960 에 제자리 패치.
#  슬롯시작 = EBOOT 포인터[3960] 동적탐색 + roff. 재빌드해도 내용불변이라 상대오프셋 안정.
#  인코딩: tbl_full_kr 2B, ASCII 1B. 널종료 + 원본 널영역까지 널패딩. avail 이내.
#  사용: py work\menu_jp\_patch.py [--check] [--dat DAT_jp_final.BIN]
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
PTR = 0x126F90
SLOT = 3960


import re
T1 = re.compile(r"<([0-9A-Fa-f]{2})>")


def enc(kr):
    out = bytearray()
    i = 0
    while i < len(kr):
        m = T1.match(kr, i)
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


def slot_start(dat, eb):
    dsz = len(dat)
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > dsz * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    return p[SLOT]


def main():
    check = "--check" in sys.argv
    datp = "DAT_jp_final.BIN"
    for a in sys.argv[1:]:
        if a.startswith("--dat="):
            datp = a.split("=", 1)[1]
    dat = bytearray(open(datp, "rb").read())
    eb = open("EBOOT_jp_new.BIN", "rb").read()
    base = slot_start(dat, eb)
    rows = json.load(open("work/menu_jp/menu_work.json", encoding="utf-8"))

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
            probs.append((r["roff"], f"인코딩불가 {bad!r}", kr))
            continue
        if len(e) + 1 > r["avail"]:
            over += 1
            probs.append((r["roff"], f"초과 {len(e)+1}>{r['avail']}", kr))
            continue
        if not check:
            off = base + r["roff"]
            dat[off:off + len(e)] = e
            for p in range(off + len(e), off + r["avail"]):
                dat[p] = 0
        ok += 1

    print(f"[{'검사' if check else '적용'}] 슬롯{SLOT}@{hex(base)} OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
    for roff, msg, kr in probs[:40]:
        print(f"  +{roff:#x}: {msg}  kr={kr!r}")
    if not check and over == 0 and err == 0:
        open(datp, "wb").write(bytes(dat))
        print(f"[OK] {datp} 슬롯{SLOT} {ok}개 갱신 (크기불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
