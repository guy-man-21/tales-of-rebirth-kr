# -*- coding: utf-8 -*-
# 스킬 속성표시 한자 -> 한글 (2026-07-19, 재배치판). 기술화면 우측 속성 라벨이 단일 한자로 표시되는데
#  폰트 회수로 水火闇 등 글리프가 한글로 희생돼 깨져 보임(水->욘, 火->꽹, 闇->걷). 風/無/雷/氷은 보존.
#  ★소스 = EBOOT 속성 데이터슬롯(@0xF74E0~, [한자2B][널2B]) + 포인터테이블(@0x148D90~).
#    실기확인: 스킬화면은 '포인터'를 읽음(포인터 재배치로 2음절 이상 표시 가능).
#  방식:
#   - 1음절(불/물): 데이터슬롯 제자리(2B) + 포인터를 원위치로 (in-place).
#   - 2음절(타격/바람/어둠): 로드되는 문자열영역 빈공간(FREE_BASE)에 기록 + 포인터 재배치.
#     ★파일 끝 널런은 RAM 미로드 -> 반드시 문자열영역(0xED000대) 빈공간 사용.
#  idempotent(고정 오프셋). 사용: py work\eboot_jp\_element_patch.py [--check] [--eboot EBOOT_jp_new.BIN]
import argparse
import json
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = {k.upper(): v for k, v in json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].items()}
INV = {v: k for k, v in Tkr.items()}
VBASE = 0x08803000
FREE_BASE = 0xED6FE        # 로드되는 문자열영역 빈공간(0xED6FD 널런 259B). 8B슬롯 x N.

# 데이터슬롯off: (포인터off, 한글, 재배치여부)
ELEMENTS = [
    (1012960, 0x148D90, "타격", True),   # 打 (물리)
    (1012964, 0x148D98, "바람", True),   # 風
    (1012968, 0x148D9C, "불",  False),   # 火  (1음절 제자리)
    (1012972, 0x148DA0, "물",  False),   # 水  (1음절 제자리)
    (1012976, 0x148DA8, "어둠", True),   # 闇
]


def enc(s):
    return b"".join(bytes.fromhex(INV[c]) for c in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()

    eb = bytearray(open(args.eboot, "rb").read())
    free = FREE_BASE
    log = []
    for data_off, ptr_off, kr, reloc in ELEMENTS:
        b = enc(kr)
        if reloc:
            slot = free
            if not args.check:
                eb[slot:slot + len(b)] = b
                eb[slot + len(b):slot + len(b) + 2] = b"\x00\x00"   # 종료
                struct.pack_into("<I", eb, ptr_off, slot + VBASE)   # 포인터 재배치
            log.append(f"  {kr}: 재배치 @{slot:#x}, 포인터 -> {slot+VBASE:#x}")
            free += 8            # 8B 슬롯(최대 3음절+널)
        else:
            if not args.check:
                eb[data_off:data_off + len(b)] = b                  # 제자리 (2B)
                eb[data_off + len(b):data_off + 2] = b""            # (안전, 2B 고정)
                struct.pack_into("<I", eb, ptr_off, data_off + VBASE)  # 포인터 원위치
            log.append(f"  {kr}: 제자리 @{data_off:#x}")
    for line in log:
        print(line)
    print(f"[{'검사' if args.check else '적용'}] 속성 {len(ELEMENTS)}개 (재배치 3 + 제자리 2)")
    if not args.check:
        open(args.eboot, "wb").write(bytes(eb))
        print(f"[OK] {args.eboot} 속성표시 한글화 (타격/바람/불/물/어둠)")


if __name__ == "__main__":
    main()
