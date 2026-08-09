#!/usr/bin/env python3
# 메인메뉴 바 항목 '가운데 정렬' (2026-07-19). 게임은 라벨을 고정 X 좌측정렬로 그림 ->
#  한국어가 일본어보다 짧으면 왼쪽 쏠림. pad(=jplen-krlen)를 앞뒤 반각공백(0x20)으로 반씩 분배.
#  ★반각공백 ~= 한글 반글자폭이라 균등분할 = 정확한 가운데. 크기·널구조 불변(뒤공백채움과 동일 안전).
#  ★대상 = 큐레이트된 메인메뉴 라벨만(리스트/스탯 화면은 좌측정렬 의도라 제외).
#  사용: py work\menu_jp\_center_menu.py [--check] [--dat DAT_jp_final.BIN]
import argparse
import json
import os
import re
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
T = re.compile(r"<([0-9A-Fa-f]{2})>")
PTR = 0x126F90
SLOT = 3960

# 가운데 정렬할 메인메뉴 라벨 (jp 원문 기준)
CENTER = {"アイテム", "エンハンス", "装備", "作戦", "料理", "カスタム", "バトルブック",
          "ステータス", "中断", "ロード", "セーブ", "術技", "ライブラリ", "あらすじ",
          "武具継承", "宝石合成", "サウンドモード", "ロード", "GRADE SHOP"}
# ★센터링 제외 roff: 무기점 등 좌측정렬 목록이 읽는 사본 (2026-07-30 실기 확인 - 무기점
#  인핸스가 앞공백 2개만큼 들여쓰여 보였음. 해당 사본은 kr+뒤공백 좌측정렬 유지)
EXCLUDE_ROFF = {0x105A6}


def enc(kr):
    o = bytearray()
    i = 0
    while i < len(kr):
        m = T.match(kr, i)
        if m:
            o.append(int(m.group(1), 16))
            i = m.end()
            continue
        c = kr[i]
        if c in inv:
            o += struct.pack(">H", inv[c])
        elif ord(c) < 0x80:
            o.append(ord(c))
        else:
            return None
        i += 1
    return bytes(o)


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

    src = open("DAT.BIN", "rb").read()
    sp = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    dat = bytearray(open(args.dat, "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    sbase, dbase = sp[SLOT], dp[SLOT]

    rows = json.load(open("work/menu_jp/menu_work.json", encoding="utf-8"))
    ok = skip = 0
    for r in rows:
        if r["jp"] not in CENTER or r["roff"] in EXCLUDE_ROFF:
            continue
        kr = (r.get("kr") or "").strip()
        if not kr:
            continue
        # jplen (원본)
        i = sbase + r["roff"]
        jl = 0
        while src[i] != 0:
            step = 2 if src[i] >= 0x81 else 1
            jl += step
            i += step
        e = enc(kr)
        if e is None or len(e) > jl:
            skip += 1
            continue
        pad = jl - len(e)
        if pad == 0:
            continue
        lead = pad // 2
        trail = pad - lead
        filled = b" " * lead + e + b" " * trail
        doff = dbase + r["roff"]
        if not args.check:
            dat[doff:doff + jl] = filled
        ok += 1
        print(f"  {r['jp']!r}->{kr!r}: pad {pad}B (앞{lead}+뒤{trail})")

    print(f"[{'검사' if args.check else '적용'}] 가운데정렬 {ok}건 / 스킵 {skip}")
    if not args.check and ok:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯{SLOT} 메뉴 가운데정렬 (크기·널구조 불변)")


if __name__ == "__main__":
    main()
