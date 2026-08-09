#!/usr/bin/env python3
# JP EBOOT 아이템 테이블(이름+설명 교차) 추출. 0xFDBF0~0x106493.
#  <01> 개행 태그 보존. avail = 다음 비널까지.
#  출력: work/item_jp/item_work.json  ([{off,avail,jp,kr,kind}])
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tall = json.load(open("tbl_all.json", encoding="utf-8"))
Tall = Tall.get("TBL", Tall)
eb = open("ULJS00132_EBOOT.BIN", "rb").read()
LO, HI = 0xFDBF0, 0x106500


def decstr(off):
    s = ""
    i = off
    unk = 0
    jp = 0
    while i < len(eb) - 1:
        c = eb[i]
        if c == 0:
            break
        if c >= 0x81:
            code = (c << 8) | eb[i + 1]
            v = Tall.get(f"{code:04X}")
            if v:
                s += v
                if "぀" <= v <= "ヿ" or "一" <= v <= "鿿" or v in "・ー":
                    jp += 1
            else:
                s += "?"
                unk += 1
            i += 2
        elif c == 1:
            s += "<01>"
            i += 1
        elif 0x20 <= c < 0x7f:
            s += chr(c)
            i += 1
        else:
            s += "?"
            unk += 1
            i += 1
    return s, i, unk, jp


def avail(off):
    i = off
    while eb[i] != 0:
        i += 2 if eb[i] >= 0x81 else 1
    e = i
    while e < len(eb) and eb[e] == 0:
        e += 1
    return e - off


def main():
    rows = []
    i = LO
    idx = 0
    while i < HI:
        if eb[i] == 0:
            i += 1
            continue
        s, e, unk, jp = decstr(i)
        if unk == 0 and jp >= 1 and len(s) >= 1:
            # 교차: 짝수번째=이름, 홀수번째=설명 (대략)
            kind = "name" if "<01>" not in s and len(s) < 16 else "desc"
            rows.append({"off": i, "avail": avail(i), "jp": s, "kr": "", "kind": kind})
            idx += 1
        i = e + 1
    out = "work/item_jp/item_work.json"
    if os.path.exists(out):
        old = {r["off"]: r["kr"] for r in json.load(open(out, encoding="utf-8"))}
        for r in rows:
            if old.get(r["off"]):
                r["kr"] = old[r["off"]]
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    names = sum(1 for r in rows if r["kind"] == "name")
    print(f"아이템 문자열 {len(rows)}개 (이름~{names}, 설명~{len(rows)-names}) -> {out}")


if __name__ == "__main__":
    main()
