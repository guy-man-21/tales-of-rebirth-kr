#!/usr/bin/env python3
# 슬롯3969(줄거리/あらすじ, 압축 커스텀포맷) 텍스트조각 추출.
#  해제 -> 문자열영역의 가나포함 널종료 조각 추출. 제어바이트(<XX>)·<01> 태그화.
#  제자리 방식: kr 은 각 조각의 원문 바이트길이 이내(offset table 불변).
#  출력: work/synopsis_jp/synopsis_work.json ([{off(해제상대), blen, jp, kr}])
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pythonlib.utils import comptolib

Tjp = json.load(open("tbl_all.json", encoding="utf-8"))["TBL"]
PTR = 0x126F90
SLOT = 3969
STR_LO = 0xB14


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


def find_comp(buf, lo):
    for dl in range(-64, 9):
        o = lo + dl
        if o < 0 or o + 9 > len(buf) or buf[o] not in (1, 3):
            continue
        try:
            csz = struct.unpack_from("<I", buf, o + 1)[0]
            if csz <= 0 or csz > 5_000_000:
                continue
            return comptolib.decompress_data(bytes(buf[o:o + 9 + csz]))
        except Exception:
            continue
    return None


def decode(d, off):
    """조각을 문자열로. 제어바이트->'<XX>', 2B->char. 널까지."""
    s = ""
    i = off
    blen = 0
    haskana = False
    while i < len(d) and d[i] != 0:
        c = d[i]
        if c < 0x20:
            s += "<%02X>" % c
            i += 1
            blen += 1
        elif c >= 0x81:
            v = Tjp.get("%04X" % ((c << 8) | d[i + 1]))
            s += v if v else "?"
            if v and ("぀" <= v[0] <= "ヿ" if v else False):
                haskana = True
            i += 2
            blen += 2
        else:
            s += chr(c)
            i += 1
            blen += 1
    return s, blen, haskana


def main():
    src = open("DAT.BIN", "rb").read()
    src_ptrs = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    d = find_comp(src, src_ptrs[SLOT])
    if d is None:
        print("[!] 슬롯3969 해제 실패")
        return
    rows = []
    i = STR_LO
    while i < len(d):
        if d[i] == 0:
            i += 1
            continue
        st = i
        s, blen, hk = decode(d, st)
        # 가나 포함 조각만 (번역 대상). 태그전용/ASCII 조각 제외.
        import re
        core = re.sub(r"<[0-9A-Fa-f]{2}>", "", s)
        if hk and len(core) >= 1:
            rows.append({"off": st, "blen": blen, "jp": s, "kr": ""})
        i = st + blen + 1
    out = "work/synopsis_jp/synopsis_work.json"
    os.makedirs("work/synopsis_jp", exist_ok=True)
    if os.path.exists(out):
        old = {r["off"]: r["kr"] for r in json.load(open(out, encoding="utf-8"))}
        for r in rows:
            if old.get(r["off"]):
                r["kr"] = old[r["off"]]
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[OK] 슬롯3969 줄거리 조각 {len(rows)}개 (해제len {len(d)}) -> {out}")


if __name__ == "__main__":
    main()
