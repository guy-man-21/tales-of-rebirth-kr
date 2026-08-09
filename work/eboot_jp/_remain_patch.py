#!/usr/bin/env python3
# EBOOT 잔여 미번역 165건 (배틀북 장문/몬스터힌트/필드메시지/귀중품설명/칭호 등) 적용.
#  scratchpad rbatch_*_kr.json 병합 -> 태그 개수 검증 -> kr+공백 '정확히 jplen' 채움(널구조 보존).
#  kr>jplen 은 공백제거 자동치유 -> 그래도 초과면 스킵 리포트.
#  사용: py work\eboot_jp\_remain_patch.py --batches <dir> [--check] [--eboot EBOOT_jp_new.BIN]
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
TAGS = re.compile(r"<[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{4}>")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()

    orig = open("ULJS00132_EBOOT.BIN", "rb").read()
    eb = bytearray(open(args.eboot, "rb").read())

    rows = []
    for f in sorted(glob.glob(os.path.join(args.batches, "rbatch_*_kr.json"))):
        rows += json.load(open(f, encoding="utf-8"))
    print(f"배치 로드: {len(rows)}행")

    ok = healed = skip = err = tagbad = 0
    probs = []
    for r in rows:
        off, L, jp = r["off"], r["len"], r["jp"]
        kr = (r.get("kr") or "").strip()
        if not kr:
            skip += 1
            continue
        # 안전: 원본과 신본이 아직 동일한 자리만 (다른 패치와 충돌 방지)
        if bytes(eb[off:off + L]) != orig[off:off + L]:
            skip += 1
            probs.append((off, "이미 패치됨", kr))
            continue
        # 태그 개수 검증
        tj = sorted(TAGS.findall(jp.upper()))
        tk = sorted(TAGS.findall(kr.upper()))
        if tj != tk:
            tagbad += 1
            probs.append((off, f"태그 불일치 jp{len(tj)}!=kr{len(tk)}", kr[:40]))
            continue
        e, badch = enc(kr)
        if e is None:
            err += 1
            probs.append((off, f"인코딩불가 {badch!r}", kr[:40]))
            continue
        was_over = len(e) > L
        while len(e) > L and " " in kr:
            kr = kr[::-1].replace(" ", "", 1)[::-1]
            e, _ = enc(kr)
        if len(e) > L:
            err += 1
            probs.append((off, f"초과 {len(e)}>{L}", kr[:40]))
            continue
        if was_over:
            healed += 1
        if not args.check:
            eb[off:off + L] = e + b" " * (L - len(e))
        ok += 1

    print(f"[{'검사' if args.check else '적용'}] OK {ok} (치유 {healed}) / 스킵 {skip} / 태그불일치 {tagbad} / 에러 {err}")
    for off, m, k in probs[:30]:
        print(f"  @{off:#x}: {m}  {k!r}")
    if not args.check and ok:
        open(args.eboot, "wb").write(bytes(eb))
        print(f"[OK] -> {args.eboot}")


if __name__ == "__main__":
    main()
