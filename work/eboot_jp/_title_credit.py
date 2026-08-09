# -*- coding: utf-8 -*-
# 타이틀 화면 저작권 줄에 번역 크레딧 추가 (2026-08-09)
#   원문 @0xF4C6C : '＄ いのまたむつみ<01>＄ 2004 2008<8140>NBGI'  (＄ = © 글리프, <01> = 개행)
#   ★이 구역 문자열은 EBOOT 안에 절대 포인터가 없다(코드가 다른 방식으로 참조).
#     재배치가 불가능하므로 뒤따르는 디버그 문자열 자리로 '제자리 확장'한다.
#     희생: 'sys/title.c'(__FILE__), 'menu_cmem %d %d\n'(디버그 printf) — 표시 텍스트 아님.
#     'Free Memory: %d K\n'(@1002676) 이후는 건드리지 않는다.
#   ★3행으로 만들지 않는 이유: 화면상 © 두 줄이 이미 바닥에 붙어 있어 셋째 줄이 잘린다.
#     그래서 크레딧은 이름과 같은 줄에 전각공백으로 띄워 붙인다.
#   ★★전각공백(0x8140)은 코드 테이블에 '없는' 특수 코드다. 반드시 원바이트로 쓸 것.
#     tbl 역매핑으로 인코딩하면 '　'으로 디코드되는 '빈 글리프 슬롯'(EC5F 등)이 잡히고
#     화면에 쓰레기 글자가 찍힌다 (2026-08-09 실기: '2008　NBGI' 가 '20(NBGI' 로 보였음).
#   ★2행은 JP 원본 바이트를 그대로 복사해 손대지 않는다.
#   idempotent: 몇 번을 실행해도 같은 결과.
import json
import os
import sys

os.chdir(r"D:\clean_project")

OFF = 1002604          # 0xF4C6C
NL = 1002604 + 17      # JP 문자열의 <01> 위치 (1행 끝)
END = 1002604 + 36     # JP 문자열 끝
LIMIT = 1002675        # 여기(포함)까지만 사용. 1002676 'Free Memory' 는 보존
NAME = "이노마타 무츠미"        # 원문 いのまたむつみ + 띄어쓰기
CREDIT = "한글화 by 기마누엘"
FWSP = b"\x81\x40"     # 전각공백 (특수 코드)
GAP = 14               # 이름과 크레딧 사이 '반각' 공백 수 = 크레딧을 오른쪽으로 미는 양.
#   ★이 폰트에서 전각공백(0x8140)은 약 6px 로 좁게 그려지고 반각공백(0x20)이 더 넓다.
#     즉 반각이 바이트당 이동량이 두 배라, 미는 용도로는 반각을 쓴다(실기 실측).
#   화면 폭 480px. 12칸이면 크레딧이 우측에 붙고 총 66B 로 여유(71B) 안에 들어간다.
#   더 밀려면 GAP 를 올리되, 71B 를 넘기면 'Free Memory' 문자열까지 희생해야 하므로
#   LIMIT 를 1002694 로 올릴 것. 과하게 밀면 화면 밖으로 잘리니 한 번에 2~3칸씩.

TBL = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
ENC = {v: k for k, v in TBL.items()}


def enc(s):
    out = bytearray()
    for ch in s:
        if ord(ch) < 0x80:
            out.append(ord(ch))
            continue
        if ch == "\u3000":
            raise SystemExit("[!] 전각공백은 FWSP 원바이트를 쓸 것")
        code = ENC.get(ch)
        if not code:
            raise SystemExit("[!] 회수 폰트에 없는 글자: %r" % ch)
        out += bytes.fromhex(code)
    return bytes(out)


def dec(b):
    s, i = "", 0
    while i < len(b) and b[i]:
        c = b[i]
        if c < 0x20:
            s += "<%02X>" % c
            i += 1
        elif c < 0x80:
            s += chr(c)
            i += 1
        else:
            code = "%04X" % ((c << 8) | b[i + 1])
            s += "<%s>" % code if code == "8140" else (TBL.get(code) or "?")
            i += 2
    return s


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "EBOOT_jp_new.BIN"
    buf = bytearray(open(path, "rb").read())
    jp = open("ULJS00132_EBOOT.BIN", "rb").read()

    head = jp[OFF:OFF + 3]              # '＄' + 반각공백
    line2 = jp[NL:END]                  # <01> + '＄ 2004 2008<8140>NBGI' (원본 그대로)
    assert head[2] == 0x20 and jp[NL] == 0x01, "JP 원본 레이아웃 불일치"

    new = head + enc(NAME) + b" " * GAP + enc(CREDIT) + line2
    room = LIMIT - OFF
    print("현재 : %r" % dec(buf[OFF:buf.find(b"\x00", OFF)]))
    print("새것 : %r  (%dB / 여유 %dB)" % (dec(new), len(new), room))
    if len(new) > room:
        raise SystemExit("[!] %dB 초과 - 문구를 줄일 것" % (len(new) - room))

    buf[OFF:LIMIT + 1] = new + b"\x00" * (LIMIT + 1 - OFF - len(new))
    assert buf[1002676] != 0, "다음 문자열(Free Memory) 훼손"
    open(path, "wb").write(bytes(buf))
    print("[OK] %s" % path)


if __name__ == "__main__":
    main()
