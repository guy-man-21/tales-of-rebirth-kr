#!/usr/bin/env python3
# desc_work.json(kr) -> EBOOT 제자리. <01>=1B, <XXXX>=2B, 회수2B, ASCII1B. avail 이내.
# 사용: py work\eboot_jp\_desc_patch.py [--check] [--eboot=EBOOT_jp_new.BIN]
import json, os, re, struct, sys
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
T4 = re.compile(r"<([0-9A-Fa-f]{4})>"); T2 = re.compile(r"<([0-9A-Fa-f]{2})>")
def enc(kr):
    out = bytearray(); i = 0
    while i < len(kr):
        m = T4.match(kr, i)
        if m: out += struct.pack(">H", int(m.group(1), 16)); i = m.end(); continue
        m = T2.match(kr, i)
        if m: out.append(int(m.group(1), 16)); i = m.end(); continue
        c = kr[i]
        if c in inv: out += struct.pack(">H", inv[c]); i += 1; continue
        if ord(c) < 0x80: out.append(ord(c)); i += 1; continue
        return None, c
    return bytes(out), None
def main():
    check = "--check" in sys.argv; ebp = "EBOOT_jp_new.BIN"
    for x in sys.argv[1:]:
        if x.startswith("--eboot="): ebp = x.split("=", 1)[1]
    eb = bytearray(open(ebp, "rb").read())
    rows = json.load(open("work/eboot_jp/desc_work.json", encoding="utf-8"))
    ok = skip = over = err = 0; probs = []
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr: skip += 1; continue
        e, bad = enc(kr)
        if e is None: err += 1; probs.append((r["off"], f"인코딩불가 {bad!r}", kr)); continue
        if len(e) + 1 > r["avail"]: over += 1; probs.append((r["off"], f"초과 {len(e)+1}>{r['avail']}", kr)); continue
        if not check:
            o = r["off"]; eb[o:o+len(e)] = e
            for p in range(o+len(e), o+r["avail"]): eb[p] = 0
        ok += 1
    print(f"[{'검사' if check else '적용'}] OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
    for o, m, k in probs[:40]: print(f"  @{o:#x}: {m}  kr={k!r}")
    if not check and over == 0 and err == 0:
        open(ebp, "wb").write(bytes(eb)); print(f"[OK] {ebp} 설명문 {ok}개 갱신")
main()
