# -*- coding: utf-8 -*-
# 도감 분류 獣 -> 짐승 (포인터 재배치). idempotent.
#  - JP 0xF75C4 = 獣(2B) 슬롯. 구패치 잔재 '식'(e297) 또는 원문이 있어도 무관 (포인터만 이동).
#  - 재배치처 = 0xED780 (로드되는 문자열 영역 널런, 0xED800 한계).
#  - 포인터 @0x148E00 (u32 vaddr, vaddr = fileoff + 0x08803000).
import json
import os
import struct
import sys

os.chdir(r"D:\clean_project")
EB = "EBOOT_jp_new.BIN"
DST = 0xED780
PTR = 0x148E00
VADDR = DST + 0x08803000
TKR = {k.lower(): v for k, v in json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].items()}
INV = {v: k for k, v in TKR.items()}
KR = "짐승"
kb = bytes.fromhex("".join(INV[c] for c in KR))

buf = bytearray(open(EB, "rb").read())
old = struct.unpack_from("<I", buf, PTR)[0]
if old not in (0xF75C4 + 0x08803000, VADDR):
    print(f"[STOP] ptr @0x{PTR:X} unexpected: 0x{old:X}")
    sys.exit(1)
# 재배치처 선점검: 비었거나(널) 이미 우리가 쓴 값
cur = bytes(buf[DST:DST + len(kb) + 1])
if cur != b"\x00" * (len(kb) + 1) and cur != kb + b"\x00":
    print(f"[STOP] dst @0x{DST:X} occupied: {cur.hex()}")
    sys.exit(1)
buf[DST:DST + len(kb)] = kb
buf[DST + len(kb)] = 0
struct.pack_into("<I", buf, PTR, VADDR)
open(EB, "wb").write(bytes(buf))
print(f"[OK] beast: '{KR}' @0x{DST:X}, ptr 0x{PTR:X} -> 0x{VADDR:X}")
