# -*- coding: utf-8 -*-
# 王の盾 EBOOT 잔여 왕방패/왕의방패(공백누락) -> 왕의 방패 통일 (2026-07-23).
#  씬 화자명(names_npc.json)·「」제목류는 이미 왕의 방패. EBOOT 콘텐츠 4곳만 불일치:
#   - 1009552 왕의방패전(제자리, jplen18 여유) / 1016988 왕방패병사·1017000 왕방패도술사·
#     1102772 전왕의방패 (예산초과 -> 포인터 재배치, 로드영역 빈공간 0xED718~).
#  ★재배치 빈공간 = 로드되는 문자열영역(속성라벨 0xED6FE~0xED715 뒤). idempotent(고정오프셋).
#  사용: py work\eboot_jp\_kingsshield_patch.py [--check]
import argparse
import json
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = {k.upper(): v for k, v in json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].items()}
INV = {v: k for k, v in Tkr.items()}
VBASE = 0x08803000
FREE_BASE = 0xED718     # 속성라벨(0xED6FE~0xED715) 뒤 빈공간(0xED6FD 널런 259B 내)


def enc(s):
    o = bytearray()
    for c in s:
        if c == " ":
            o.append(0x20)
        else:
            o += bytes.fromhex(INV[c])
    return bytes(o)


# 제자리: (data_off, kr, jplen)
INPLACE = [(1009552, "왕의 방패전", 18)]
# 재배치: (kr, [ptr_off,...])
RELOC = [
    ("왕의 방패 병사", [0x14947C]),
    ("왕의 방패 도술사", [0x149480]),
    ("전 왕의 방패", [0xD0E1E, 0x153A44]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()
    eb = bytearray(open(args.eboot, "rb").read())

    log = []
    for off, kr, jl in INPLACE:
        b = enc(kr)
        assert len(b) <= jl, (kr, len(b), jl)
        if not args.check:
            eb[off:off + len(b)] = b
            eb[off + len(b)] = 0            # 널 종료
        log.append(f"  제자리 @{off:#x}: {kr!r} ({len(b)}B/{jl})")

    free = FREE_BASE
    for kr, ptrs in RELOC:
        b = enc(kr)
        if not args.check:
            eb[free:free + len(b)] = b
            eb[free + len(b):free + len(b) + 2] = b"\x00\x00"
            for p in ptrs:
                struct.pack_into("<I", eb, p, free + VBASE)
        log.append(f"  재배치 @{free:#x}: {kr!r} -> 포인터 {[hex(p) for p in ptrs]}")
        free += len(b) + 2

    for line in log:
        print(line)
    print(f"[{'검사' if args.check else '적용'}] 제자리 {len(INPLACE)} + 재배치 {len(RELOC)} "
          f"(빈공간 {FREE_BASE:#x}~{free:#x})")
    if not args.check:
        open(args.eboot, "wb").write(bytes(eb))
        print(f"[OK] {args.eboot} 왕의 방패 통일")


if __name__ == "__main__":
    main()
