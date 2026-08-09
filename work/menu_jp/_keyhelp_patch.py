#!/usr/bin/env python3
# 슬롯3960 KEY HELP/액션라벨 전수 치환 (화면마다 복사본 = 다수 인스턴스).
#  menu_work 번역을 사전으로, 슬롯 전체에서 '단독 라벨' 인스턴스를 같은길이 제자리 치환.
#  단독 판정: 용어 바로 앞=0x00, 바로 뒤=(0x00 or 제어<0x20 or 전각공백 8140).
#  kr 바이트<=jp 바이트 (부족분 공백). 널구조·주변 완전 보존. 미매칭/초과는 건드리지 않음.
#  사용: py work\menu_jp\_keyhelp_patch.py [--check] [--dat DAT_jp_final.BIN]
import argparse
import json
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tjp = json.load(open("tbl_all.json", encoding="utf-8"))["TBL"]
revjp = {v: k for k, v in Tjp.items()}
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
invkr = {v: int(k, 16) for k, v in Tkr.items()}
PTR = 0x126F90
SLOT = 3960


def enc_jp(s):
    o = bytearray()
    for ch in s:
        if ch in revjp:
            o += bytes.fromhex(revjp[ch])
        elif ord(ch) < 0x80:
            o.append(ord(ch))
        else:
            return None
    return bytes(o)


def enc_kr(s):
    o = bytearray()
    for ch in s:
        if ch in invkr:
            o += struct.pack(">H", invkr[ch])
        elif ord(ch) < 0x80:
            o.append(ord(ch))
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

    dat = bytearray(open(args.dat, "rb").read())
    eb = open("EBOOT_jp_new.BIN", "rb").read()
    p = read_ptrs(eb, len(dat))
    lo, hi = p[SLOT], p[SLOT + 1]

    # 사전: menu_work {jp: kr}, kr 인코딩 <= jp 인코딩 인 것만
    rows = json.load(open("work/menu_jp/menu_work.json", encoding="utf-8"))
    D = {}
    for r in rows:
        jp = r["jp"]
        kr = (r.get("kr") or "").strip()
        if not kr or "<" in jp:      # 태그 포함 jp 는 단순치환 제외(복잡)
            continue
        ej, ek = enc_jp(jp), enc_kr(kr)
        if ej and ek and len(ek) <= len(ej) and len(ej) >= 2:
            D.setdefault(jp, (ej, ek))
    # KEY HELP 추가 사전 (menu_work 밖일 수 있는 것)
    EXTRA = {"あらすじブック": "줄거리 북", "決定": "결정", "戻る": "뒤로",
             "はずす": "벗기", "外す": "벗기", "キャンセル": "취소",
             "やめる": "그만", "いいえ": "아니오", "送る": "보내기", "渡す": "건네기"}
    for jp, kr in EXTRA.items():
        ej, ek = enc_jp(jp), enc_kr(kr)
        if ej and ek and len(ek) <= len(ej):
            D[jp] = (ej, ek)
    # 긴 jp 우선(부분매칭 방지)
    order = sorted(D, key=lambda k: -len(D[k][0]))

    def is_delim_after(pos):
        if pos >= hi:
            return True
        c = dat[pos]
        if c == 0 or c < 0x20:
            return True
        if c == 0x81 and pos + 1 < hi and dat[pos + 1] == 0x40:  # 전각공백 8140
            return True
        return False

    total = 0
    per = {}
    i = lo
    while i < hi:
        if dat[i] == 0:
            i += 1
            continue
        # 이 위치가 엔트리 시작(앞이 0x00)일 때만 라벨 후보
        if dat[i - 1] != 0:
            # 엔트리 중간 -> 다음 널까지 스킵
            while i < hi and dat[i] != 0:
                i += 2 if dat[i] >= 0x81 else 1
            continue
        matched = None
        for jp in order:
            ej, ek = D[jp]
            if dat[i:i + len(ej)] == ej and is_delim_after(i + len(ej)):
                matched = (jp, ej, ek)
                break
        if matched:
            jp, ej, ek = matched
            if not args.check:
                dat[i:i + len(ej)] = ek + b" " * (len(ej) - len(ek))
            total += 1
            per[jp] = per.get(jp, 0) + 1
        # 엔트리 끝으로
        while i < hi and dat[i] != 0:
            i += 2 if dat[i] >= 0x81 else 1

    print(f"[{'검사' if args.check else '적용'}] 치환 {total}건 / 용어 {len(per)}종")
    for jp, n in sorted(per.items(), key=lambda x: -x[1])[:20]:
        print(f"  {n:3}x  {jp!r} -> {D[jp][1].decode('ascii','replace') if False else ''}")
    if not args.check and total:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯{SLOT} KEY HELP {total}건 (크기·널구조 불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
