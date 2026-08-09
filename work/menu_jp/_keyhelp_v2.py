#!/usr/bin/env python3
# 슬롯3960 KEY HELP 바닥버튼 힌트 v2 — menu v2 가 커버 못 한 '추가 라벨'만 제자리 동일길이 교체.
#  ★menu v2(_patch2)는 戻る/やめる/いいえ/装備/術技/作戦 등을 이미 안전 번역(배틀OK).
#    이 도구는 그 외 決定(버튼코드형)·はずす·はい·送る·渡す·あらすじブック 만 추가.
#  ★배틀결과 크래시 원인 = 이 추가 인스턴스 중 특정 1개를 배틀결과가 데이터로 읽음(런타임 추적 불가).
#    -> 라벨 단위 토글(--only / --exclude)로 1테스트 이등분 가능하게 설계.
#  구간: UI 영역(REL 0xF000~0x13200)만. 단독(앞0x00)+뒤 delim(널/제어/전각공백). 같은길이 공백채움.
#  사용: py work\menu_jp\_keyhelp_v2.py [--check] [--only 決定,はずす] [--exclude はい] [--dat ...]
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
REL_LO = 0xF000
REL_HI = 0x13200

# menu v2 미커버(또는 부분커버) 라벨만. kr 은 jp 바이트 이내.
LABELS = {
    "決定": "결정",
    "はずす": "벗기",
    "あらすじブック": "줄거리북",
    "装備替え": "장비교체",
    "送る": "보내",
    "渡す": "건넴",
    "はい": "예",
}


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
    ap.add_argument("--only", default="")
    ap.add_argument("--exclude", default="")
    args = ap.parse_args()

    only = set(x for x in args.only.split(",") if x)
    excl = set(x for x in args.exclude.split(",") if x)
    labels = {jp: kr for jp, kr in LABELS.items()
              if (not only or jp in only) and jp not in excl}

    dat = bytearray(open(args.dat, "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    base = dp[SLOT]
    lo, hi = base + REL_LO, base + REL_HI

    def is_delim(pos):
        if pos >= hi:
            return True
        c = dat[pos]
        if c == 0 or c < 0x20:
            return True
        if c == 0x81 and pos + 1 < hi and dat[pos + 1] == 0x40:
            return True
        return False

    D = {}
    for jp, kr in labels.items():
        ej, ek = enc_jp(jp), enc_kr(kr)
        if ej and ek and len(ek) <= len(ej):
            D[jp] = (ej, ek)
        else:
            print(f"  [경고] {jp!r}->{kr!r} 인코딩/길이 문제")
    order = sorted(D, key=lambda k: -len(D[k][0]))

    per = {}
    total = 0
    for jp in order:
        ej, ek = D[jp]
        i = lo
        while i < hi:
            pos = dat.find(ej, i, hi)
            if pos < 0:
                break
            if dat[pos - 1] == 0 and is_delim(pos + len(ej)):
                if not args.check:
                    dat[pos:pos + len(ej)] = ek + b" " * (len(ej) - len(ek))
                per[jp] = per.get(jp, 0) + 1
                total += 1
            i = pos + len(ej)

    print(f"[{'검사' if args.check else '적용'}] 라벨 {len(D)}종 / 치환 {total}건")
    for jp, n in sorted(per.items(), key=lambda x: -x[1]):
        print(f"  {n:3}x  {jp!r} -> {LABELS[jp]!r}")
    if not args.check and total:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯{SLOT} KEY HELP v2 {total}건 (크기·널구조 불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
