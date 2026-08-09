#!/usr/bin/env python3
# item_work.json(kr 채움)을 JP EBOOT 에 제자리 패치. <01> 개행 태그 지원.
#  인코딩: 회수(tbl_full_kr) 2B, ASCII 1B, <XXXX> 2B값, <XX> 1B값. 널종료+널패딩.
#  각 엔트리 len(kr_bytes)+1 <= avail. 사용: py work\item_jp\_patch.py [--check] [--eboot=...]
import json
import os
import re
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
TAG4 = re.compile(r"<([0-9A-Fa-f]{4})>")
TAG2 = re.compile(r"<([0-9A-Fa-f]{2})>")


def enc(kr):
    out = bytearray()
    i = 0
    while i < len(kr):
        m = TAG4.match(kr, i)
        if m:
            out += struct.pack(">H", int(m.group(1), 16))
            i = m.end()
            continue
        m = TAG2.match(kr, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        c = kr[i]
        if c in inv:
            out += struct.pack(">H", inv[c])
            i += 1
            continue
        if ord(c) < 0x80:
            out.append(ord(c))
            i += 1
            continue
        return None, c
    return bytes(out), None


def main():
    check = "--check" in sys.argv
    ebp = "EBOOT_jp_new.BIN"
    for a in sys.argv[1:]:
        if a.startswith("--eboot="):
            ebp = a.split("=", 1)[1]
    if not os.path.exists(ebp):
        print(f"[!] {ebp} 없음")
        return
    eb = bytearray(open(ebp, "rb").read())
    rows = json.load(open("work/item_jp/item_work.json", encoding="utf-8"))
    ok = skip = over = err = 0
    probs = []
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr:
            skip += 1
            continue
        e, bad = enc(kr)
        if e is None:
            err += 1
            probs.append((r["off"], f"인코딩불가 {bad!r}", kr[:24]))
            continue
        if len(e) + 1 > r["avail"]:
            over += 1
            probs.append((r["off"], f"초과 {len(e)+1}>{r['avail']}", kr[:24]))
            continue
        if not check:
            off = r["off"]
            eb[off:off + len(e)] = e
            for p in range(off + len(e), off + r["avail"]):
                eb[p] = 0
        ok += 1
    print(f"[{'검사' if check else '적용'}] OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
    for off, msg, kr in probs[:40]:
        print(f"  @{off:#x}: {msg}  kr={kr!r}")
    if not check and over == 0 and err == 0:
        open(ebp, "wb").write(bytes(eb))
        print(f"[OK] {ebp} 아이템 {ok}개 갱신 (크기불변 {len(eb)}B)")
    elif not check:
        print("[중단] 초과/에러 있음")


if __name__ == "__main__":
    main()
