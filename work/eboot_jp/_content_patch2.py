#!/usr/bin/env python3
# EBOOT 콘텐츠(cbatch/dbatch) v2 — 널구조 보존판 (배틀 중 크래시 수정).
#  기반: 제목판 EBOOT(배틀검증) 위에, 각 번역을 kr+공백으로 '원문 jplen 정확히' 채움.
#  jplen 밖은 원본 그대로(널런 보존). kr>jplen 은 공백제거 자동치유 -> 그래도 초과면 스킵 리포트.
#  사용: py work\eboot_jp\_content_patch2.py --base=<검증EBOOT> --out=EBOOT_jp_new.BIN [--check]
import argparse
import glob
import json
import os
import re
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
T4 = re.compile(r"<([0-9A-Fa-f]{4})>")
T2 = re.compile(r"<([0-9A-Fa-f]{2})>")


def enc(kr):
    o = bytearray()
    i = 0
    while i < len(kr):
        m = T4.match(kr, i)
        if m:
            o += struct.pack(">H", int(m.group(1), 16))
            i = m.end()
            continue
        m = T2.match(kr, i)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    orig = open("ULJS00132_EBOOT.BIN", "rb").read()
    eb = bytearray(open(args.base, "rb").read())

    def jplen_at(off):
        L = 0
        i = off
        while orig[i] != 0:
            step = 2 if orig[i] >= 0x81 else 1
            L += step
            i += step
        return L

    cb_offs = set()
    for f in glob.glob("work/eboot_jp/cbatch_[0-9][0-9][0-9].json"):
        for l in json.load(open(f, encoding="utf-8"))["lines"]:
            cb_offs.add(l["off"])
    rows = json.load(open("work/eboot_jp/eboot_work.json", encoding="utf-8"))
    items = [(r["off"], r.get("kr", "")) for r in rows if r["off"] in cb_offs]
    items += [(r["off"], r.get("kr", "")) for r in
              json.load(open("work/eboot_jp/desc_work.json", encoding="utf-8"))]

    ok = healed = skip = err = 0
    probs = []
    for off, kr in items:
        kr = (kr or "").strip()
        if not kr:
            continue
        L = jplen_at(off)
        e = enc(kr)
        if e is None:
            err += 1
            probs.append((off, "인코딩불가", kr))
            continue
        was_over = len(e) > L
        while len(e) > L and " " in kr:      # 공백제거 자동치유
            kr = kr[::-1].replace(" ", "", 1)[::-1]
            e = enc(kr)
        if len(e) > L:
            skip += 1
            probs.append((off, f"초과 {len(e)}>{L}", kr))
            continue
        if was_over:
            healed += 1
        eb[off:off + L] = e + b" " * (L - len(e))   # 정확히 L, jplen 밖 불변
        ok += 1

    print(f"[{'검사' if args.check else '적용'}] OK {ok} (자동치유 {healed}) / 초과스킵 {skip} / 에러 {err}")
    for off, m, k in probs[:25]:
        print(f"  @{off:#x}: {m}  {k[:30]!r}")
    if not args.check:
        open(args.out, "wb").write(bytes(eb))
        print(f"[OK] -> {args.out}")


if __name__ == "__main__":
    main()
