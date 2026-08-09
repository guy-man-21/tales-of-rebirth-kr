#!/usr/bin/env python3
# 배틀북(슬롯16185 + 슬롯2사본 +0xAF838) 버튼코드 정렬 교정 (2026-07-19).
#  문제: '전투 중 조작' 목록 등에서 라벨 번역이 짧아 버튼코드(<0D>XX) 뒤에 공백이 붙음 ->
#  아이콘 스프라이트가 밀리고 리스트 파싱이 어긋나 행이 깨짐(△/십자키 번갈아 뜸).
#  교정: [내용]<0D><XX>[공백들] -> [내용][공백들]<0D><XX> (코드를 엔트리 끝으로).
#  크기·널구조 불변(바이트 재배치만). 사용: py work\battle_jp\_bb_fix_btnpad.py [--check]
import argparse
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PTR = 0x126F90
COPY2_OFF = 0xAF838


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


def fix_region(dat, lo, hi, apply):
    fixed = 0
    i = lo
    while i < hi:
        if dat[i] == 0:
            i += 1
            continue
        st = i
        while i < hi and dat[i] != 0:
            i += 1
        e = i
        sp = e
        while sp > st and dat[sp - 1] == 0x20:
            sp -= 1
        nsp = e - sp
        if nsp == 0:
            continue
        # 아이콘(<0D>XX)이 뒤 공백 바로 앞에 있는 엔트리만 교정 (리스트+설명 공통).
        #  ★아이콘은 반드시 엔트리 끝(널 직전)에 와야 함(파싱). 공백은 '마지막 <01> 앞'(=텍스트 줄 끝,
        #    안 보임)으로 옮김 -> 틈 없음 + 아이콘 끝 유지. <01> 없으면 아이콘 바로 앞(폴백).
        if sp - 2 >= st and dat[sp - 2] == 0x0D:
            L1 = -1
            for j in range(sp - 3, st - 1, -1):
                if dat[j] == 0x01:
                    L1 = j
                    break
            if L1 >= 0:
                newv = bytes(dat[st:L1]) + b" " * nsp + bytes(dat[L1:sp])
            else:
                newv = bytes(dat[st:sp - 2]) + b" " * nsp + bytes(dat[sp - 2:sp])
            if newv != bytes(dat[st:e]):
                if apply:
                    dat[st:e] = newv
                fixed += 1
    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    args = ap.parse_args()
    dat = bytearray(open(args.dat, "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    apply = not args.check
    b16 = dp[16185]
    e16 = dp[16186]
    n16 = fix_region(dat, b16, e16, apply)
    b2 = dp[2] + COPY2_OFF
    n2 = fix_region(dat, b2, b2 + (e16 - b16), apply)
    print(f"[{'검사' if args.check else '적용'}] 슬롯16185 {n16}건 / 슬롯2사본 {n2}건")
    if apply and (n16 or n2):
        open(args.dat, "wb").write(bytes(dat))
        print("[OK] DAT_jp_final 배틀북 버튼 정렬 교정 (크기·널구조 불변)")


if __name__ == "__main__":
    main()
