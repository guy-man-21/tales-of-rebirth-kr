#!/usr/bin/env python3
# 메뉴 슬롯3960 v2 패치 — 널 구조 완전 보존판 (배틀종료 크래시 수정).
#  원리: 원시 UI 테이블은 널 카운팅에 민감(슬롯2 STRICT 존과 동일) -> 널 채움 금지.
#  절차: (1) 슬롯3960 전체를 원본 DAT.BIN 내용으로 복원(내용 동일·roff 안정)
#        (2) 각 번역: kr + 공백(0x20)으로 '원문 바이트길이(jplen)에 정확히' 채움.
#            jplen 밖 바이트는 원본 그대로(널런/후속 구조 불변).
#  kr 인코딩 > jplen 인 행은 스킵 리포트(사전 트림 필요).
#  사용: py work\menu_jp\_patch2.py [--check] [--dat DAT_jp_final.BIN]
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
            i += 1
        elif ord(c) < 0x80:
            o.append(ord(c))
            i += 1
        else:
            return None
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
    slen = sp[SLOT + 1] - sbase
    dlen = dp[SLOT + 1] - dbase
    if slen != dlen:
        print(f"[중단] 슬롯 크기 불일치 {slen}!={dlen}")
        return

    # (1) 전체 원본 복원
    dat[dbase:dbase + dlen] = src[sbase:sbase + slen]

    # (2) 정확길이 공백채움
    rows = json.load(open("work/menu_jp/menu_work.json", encoding="utf-8"))
    ok = skip = over = err = 0
    probs = []
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr:
            skip += 1
            continue
        soff = sbase + r["roff"]
        jplen = 0
        i = soff
        while src[i] != 0:
            step = 2 if src[i] >= 0x81 else 1
            jplen += step
            i += step
        e = enc(kr)
        if e is None:
            err += 1
            probs.append((r["roff"], "인코딩불가", kr))
            continue
        if len(e) > jplen:
            over += 1
            probs.append((r["roff"], f"초과 {len(e)}>{jplen}", kr))
            continue
        filled = e + b" " * (jplen - len(e))   # 정확히 jplen
        doff = dbase + r["roff"]
        dat[doff:doff + jplen] = filled
        ok += 1

    print(f"[{'검사' if args.check else '적용'}] OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
    for roff, m, k in probs[:20]:
        print(f"  +{roff:#x}: {m}  {k!r}")
    if not args.check and err == 0:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯{SLOT} v2 갱신 (널구조 보존, 크기불변)")


if __name__ == "__main__":
    main()
