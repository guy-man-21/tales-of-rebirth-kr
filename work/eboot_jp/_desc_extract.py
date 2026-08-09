#!/usr/bin/env python3
# EBOOT 다행 설명문(\x01 줄바꿈 포함) 추출. 기존 _extract 가 제어문자로 걸러 누락한 것.
#  구역가이드/배틀북설명/줄거리/설정설명 등. \x01 -> <01> 태그로 표기.
#  아이템·배틀help 구간 제외. 출력: work/eboot_jp/desc_work.json ([{off,avail,jp,kr}])
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tjp = json.load(open("tbl_all.json", encoding="utf-8"))
Tjp = Tjp.get("TBL", Tjp)
eb = open("ULJS00132_EBOOT.BIN", "rb").read()

LO, HI = 0xEFF00, 0x118200
EXCLUDE = [(0xFDBF0, 0x106500), (0x105720, 0x105F00), (0x10FEB4, 0x10FFA0)]


def excluded(off):
    return any(lo <= off < hi for lo, hi in EXCLUDE)


def decstr(off, mx=400):
    s = ""
    i = off
    unk = 0
    while i < len(eb) - 1 and i < off + mx:
        c = eb[i]
        if c == 0:
            break
        if c == 1:
            s += "<01>"
            i += 1
            continue
        if c >= 0x81:
            v = Tjp.get("%04X" % ((c << 8) | eb[i + 1]))
            s += v if v else "?"
            unk += 0 if v else 1
            i += 2
        elif 0x20 <= c < 0x7f:
            s += chr(c)
            i += 1
        else:
            return None, i, 1   # 다른 제어문자 => 문자열 아님
    return s, i, unk


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
    while i < HI:
        if eb[i] == 0:
            i += 1
            continue
        s, e, unk = decstr(i)
        if s is not None and "<01>" in s and unk == 0 and len(s) >= 4 and not excluded(i):
            rows.append({"off": i, "avail": avail(i), "jp": s, "kr": ""})
            i = e + 1
        else:
            i = (e + 1) if s is not None else (i + 1)
    out = "work/eboot_jp/desc_work.json"
    if os.path.exists(out):
        old = {r["off"]: r["kr"] for r in json.load(open(out, encoding="utf-8"))}
        for r in rows:
            if old.get(r["off"]):
                r["kr"] = old[r["off"]]
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[OK] 다행 설명문 {len(rows)}개 -> {out}")


if __name__ == "__main__":
    main()
