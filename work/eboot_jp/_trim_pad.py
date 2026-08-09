# -*- coding: utf-8 -*-
# 요리명/칭호명 테이블 꼬리공백 트림 (2026-07-30). idempotent.
#  증상: 칭호 획득 notice 『나이스 웨이터   』 / 요리명 뒤 공백 등 - 구패처의 jplen 공백패딩이
#  런타임 이름삽입(<0c>류)에서 그대로 보임.
#  범위 = 0x10A800~0x10DC00 (요리명/레시피설명/자동요리설정/칭호명/칭호설명 블록).
#  ★이 블록은 접미사 포인터 재사용(샌드위치/모험가/여왕 등)이 실증된 곳 = 포인터 전용 참조
#   -> 꼬리공백->널 전환이 서수/널카운트 참조를 깨지 않음. (배틀 기술명/유닛명 테이블은 범위 밖 - 금지)
#  ★파이프라인 말미(_remain_patch/_content_patch2 이후) 실행 - 그 패처들이 공백패딩을 재생성함.
import os
import sys

os.chdir(r"D:\clean_project")
EB = "EBOOT_jp_new.BIN"
LO, HI = 0x10A800, 0x10DC00

buf = bytearray(open(EB, "rb").read())
q = LO
n = trimmed = 0
while q < HI:
    if buf[q] == 0:
        q += 1
        continue
    st = q
    while q < HI and buf[q] != 0:
        q += 1
    en = q
    e2 = en
    while e2 > st and buf[e2 - 1] == 0x20:
        e2 -= 1
    if e2 == st:
        continue  # 전부 공백(의도적 블랭크 슬롯) = 유지
    if e2 < en:
        buf[e2:en] = b"\x00" * (en - e2)
        trimmed += 1
        n += en - e2
open(EB, "wb").write(bytes(buf))
print(f"[OK] trim_pad: {trimmed} strings, {n} bytes 0x20->0x00 in 0x{LO:X}~0x{HI:X}")
