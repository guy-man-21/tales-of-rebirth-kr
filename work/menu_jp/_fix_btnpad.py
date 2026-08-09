#!/usr/bin/env python3
# 슬롯3960 KEY HELP 버튼 정렬 교정 (2026-07-19). 문제: 라벨 번역 시 kr 이 jp 보다 짧으면
#  패처가 '버튼코드(<8140><0D>XX) 뒤'에 공백을 채워 버튼 스프라이트가 왼쪽으로 밀림(하단바 뒤죽박죽).
#  교정: [내용][버튼코드그룹][공백들] -> [내용][공백들][버튼코드그룹] 으로 스왑.
#  버튼코드그룹 = 끝부분의 [<8140>?] <0D> <1byte>. 공백을 그 앞으로 옮기면 버튼 오프셋이 JP 원본과 일치.
#  크기·널구조 완전 불변(바이트 재배치만). 사용: py work\menu_jp\_fix_btnpad.py [--check]
import argparse
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PTR = 0x126F90
SLOT = 3960
REL_LO = 0xE000
REL_HI = 0x13200


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    args = ap.parse_args()

    dat = bytearray(open(args.dat, "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    base = dp[SLOT]
    lo, hi = base + REL_LO, base + REL_HI

    fixed = 0
    samples = []
    i = lo
    while i < hi:
        if dat[i] == 0:
            i += 1
            continue
        st = i
        while i < hi and dat[i] != 0:
            i += 1
        e = i                                  # [st, e) = 엔트리
        # 끝 공백런
        sp = e
        while sp > st and dat[sp - 1] == 0x20:
            sp -= 1
        nsp = e - sp                           # 트레일링 공백 개수
        if nsp == 0:
            continue
        # 공백 바로 앞이 버튼코드? [<0D>][XX] (앞에 <8140> 옵션)
        # sp-2 = 0x0D ? (XX=sp-1)
        if sp - 2 >= st and dat[sp - 2] == 0x0D:
            cg = sp - 2                         # 코드그룹 시작
            if cg - 2 >= st and dat[cg - 2] == 0x81 and dat[cg - 1] == 0x40:
                cg -= 2                         # <8140> 포함
            # [st..cg)=내용, [cg..sp)=코드그룹, [sp..e)=공백
            content = bytes(dat[st:cg])
            group = bytes(dat[cg:sp])
            spaces = b" " * nsp
            newv = content + spaces + group     # 공백을 코드그룹 앞으로
            if newv != bytes(dat[st:e]):
                if not args.check:
                    dat[st:e] = newv
                fixed += 1
                if len(samples) < 12:
                    samples.append((st - base, group.hex(), nsp))

    print(f"[{'검사' if args.check else '적용'}] 버튼정렬 교정 {fixed}건")
    for roff, g, n in samples:
        print(f"  +{roff:#x}: 코드그룹 {g} / 공백 {n}개 앞으로 이동")
    if not args.check and fixed:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯{SLOT} 버튼 정렬 교정 (크기·널구조 불변)")


if __name__ == "__main__":
    main()
