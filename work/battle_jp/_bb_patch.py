#!/usr/bin/env python3
# 배틀북 콘텐츠(슬롯16185, 44,620B raw) 한글 제자리 패치 (2026-07-18).
#  FG게이지 설명·전투 조언·용어 해설 등 218행. ★같은 파일의 raw 사본이 슬롯2+0xAF838 에도
#  존재 -> 두 곳 모두 동일 적용. kr+공백 '정확히 len' 채움(널구조 보존), 태그개수 검증.
#  배치: scratchpad bb_1_kr.json/bb_2_kr.json (오프셋 = 슬롯16185 상대).
#  ★슬롯2 쪽은 압축 스트림1 밖(꼬리 raw 구역)이라 재압축 불필요·오버레이 불변.
#  사용: py work\battle_jp\_bb_patch.py --batches <dir> [--check]
import argparse
import glob
import json
import os
import re
import struct

os.chdir(r"D:\clean_project")
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
T4 = re.compile(r"<([0-9A-Fa-f]{4})>")
T2 = re.compile(r"<([0-9A-Fa-f]{2})>")
TAGS = re.compile(r"<[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{4}>")
PTR = 0x126F90
COPY2_OFF = 0xAF838      # 슬롯2 내 사본 시작 (슬롯16185[0] == 슬롯2+0xAF838)


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
        elif ord(c) < 0x80:
            o.append(ord(c))
        else:
            return None, c
        i += 1
    return bytes(o), None


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
    ap.add_argument("--batches", default="work/battle_jp/bb_batch")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    jp = open("DAT.BIN", "rb").read()
    pj = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(jp))
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    pn = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    base16 = pn[16185]
    base2 = pn[2] + COPY2_OFF
    obase16 = pj[16185]

    rows = []
    for f in sorted(glob.glob(os.path.join(args.batches, "bb_*_kr.json"))):
        rows += json.load(open(f, encoding="utf-8"))
    print(f"배치 {len(rows)}행")

    ok = skip = tagbad = err = over = c2 = 0
    probs = []
    for r in rows:
        off, L, jptxt = r["off"], r["len"], r["jp"]
        kr = (r.get("kr") or "").strip()
        if not kr:
            skip += 1
            continue
        tj = sorted(TAGS.findall(jptxt.upper()))
        tk = sorted(TAGS.findall(kr.upper()))
        if tj != tk:
            tagbad += 1
            probs.append((off, f"태그 {len(tj)}!={len(tk)}", kr[:36]))
            continue
        e, bad = enc(kr)
        if e is None:
            err += 1
            probs.append((off, f"인코딩불가 {bad!r}", kr[:36]))
            continue
        was = len(e) > L
        while len(e) > L and " " in kr:
            kr = kr[::-1].replace(" ", "", 1)[::-1]
            e, _ = enc(kr)
        if len(e) > L:
            over += 1
            probs.append((off, f"초과 {len(e)}>{L}", kr[:36]))
            continue
        orig = jp[obase16 + off:obase16 + off + L]
        filled = e + b" " * (L - len(e))
        # 슬롯16185
        if bytes(dat[base16 + off:base16 + off + L]) == orig:
            if not args.check:
                dat[base16 + off:base16 + off + L] = filled
            ok += 1
        # 슬롯2 사본
        if bytes(dat[base2 + off:base2 + off + L]) == orig:
            if not args.check:
                dat[base2 + off:base2 + off + L] = filled
            c2 += 1
    print(f"[{'검사' if args.check else '적용'}] 16185:{ok} / 슬롯2사본:{c2} / 빈칸 {skip} "
          f"/ 태그불일치 {tagbad} / 초과 {over} / 에러 {err}")
    for off, m, k in probs[:20]:
        print(f"  +{off:#x}: {m}  {k!r}")
    if not args.check and (ok or c2):
        open("DAT_jp_final.BIN", "wb").write(bytes(dat))
        print("[OK] DAT_jp_final 배틀북 패치 (크기불변)")


if __name__ == "__main__":
    main()
