# -*- coding: utf-8 -*-
# 접미사 포인터 일괄 교정 (2026-07-30). idempotent.
#  JP 는 장비분류/기술명/칭호/속성 라벨을 긴 아이템명·기술명의 '접미사'(문자열 중간 포인터)로
#  재사용하는데, 한글 이름이 짧아지거나 정렬이 달라져 라벨이 빈칸/깨짐(로드 빈칸, 너클->'<83>',
#  메일->'O일', 모험가->'b험가' 등). 수정 = 포인터를 빈공간의 독립 한글 라벨로 재배치.
#  ★0x128EB8/0x128EBC 는 JP 기준으로도 문자 중간 = 텍스트 포인터 아님(데이터) -> 절대 금지.
#  재배치 영역: 0xED786~0xED7FF (0xED780~5 는 _beast_patch '짐승' 사용).
import json
import os
import struct
import sys

os.chdir(r"D:\clean_project")
EB = "EBOOT_jp_new.BIN"
JP = "ULJS00132_EBOOT.BIN"
BASE = 0xED786
LIMIT = 0xED800
VBASE = 0x08803000
TKR = {k.lower(): v for k, v in json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].items()}
INV = {v: k for k, v in TKR.items()}


def enc(s):
    return bytes.fromhex("".join(INV[c] for c in s))


# (라벨, [포인터 필드 오프셋...]) — 라벨은 기존 번역 표기와 일치시킬 것
FIXES = [
    ("땅",      [0x148D94]),            # 속성 地 (몬스터 내성 등)
    ("슛",      [0x149780]),            # シュート (어설트 슛 기준)
    ("브레이크", [0x149810, 0x14E784]),  # ブレイク
    ("드레인",  [0x149830]),            # ドレイン
    ("차지",    [0x14E7C0]),            # チャージ
    ("로드",    [0x14F014]),            # ロッド (무기점 이름 빈칸의 범인)
    ("셉터",    [0x14F030]),            # セプター (리릭 셉터 기준)
    ("너클",    [0x14546C]),
    ("카드",    [0x1454C8, 0x14F51C]),
    ("아머",    [0x145580]),
    ("재킷",    [0x1455DC]),
    ("메일",    [0x145638]),
    ("클로크",  [0x145694]),
    ("로브",    [0x14574C]),
    ("톤파",    [0x145358]),            # 앞공백 표시 교정
    ("플레이트", [0x1456F0]),           # 앞공백 표시 교정
    ("샌드위치", [0x152E84]),
    ("모험가",  [0x1533FC, 0x153558, 0x1536C0, 0x15381C, 0x153978, 0x153AEC]),
    ("여왕",    [0x153BAC, 0x153BE8]),
    # 2026-07-30 추가: 杖 분류 라벨 (JP 접미사 타깃이 KR 에서 우연히 글자경계('얽')라 1차 탐지 누락)
    ("지팡이",  [0x145410]),
]

jp = open(JP, "rb").read()
buf = bytearray(open(EB, "rb").read())
cur = BASE
alloc = {}
for label, ptrs in FIXES:
    kb = enc(label)
    need = len(kb) + 1
    if cur + need > LIMIT:
        print(f"[STOP] free space exhausted at {label}")
        sys.exit(1)
    dst = cur
    exist = bytes(buf[dst:dst + need])
    if exist != kb + b"\x00" and exist != b"\x00" * need:
        print(f"[STOP] dst @0x{dst:X} occupied: {exist.hex()}")
        sys.exit(1)
    buf[dst:dst + len(kb)] = kb
    buf[dst + len(kb)] = 0
    va = dst + VBASE
    for p in ptrs:
        old = struct.unpack_from("<I", buf, p)[0]
        jold = struct.unpack_from("<I", jp, p)[0]
        if old not in (jold, va):
            print(f"[STOP] ptr @0x{p:X} unexpected 0x{old:X} (JP 0x{jold:X})")
            sys.exit(1)
        struct.pack_into("<I", buf, p, va)
    alloc[label] = dst
    cur += need
open(EB, "wb").write(bytes(buf))
print(f"[OK] suffix pointers: {len(FIXES)} labels, {sum(len(v) for _, v in FIXES)} ptrs, "
      f"alloc 0x{BASE:X}~0x{cur - 1:X} (free {LIMIT - cur}B)")
