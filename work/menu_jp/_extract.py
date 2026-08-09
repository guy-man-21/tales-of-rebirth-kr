#!/usr/bin/env python3
# DAT 슬롯 3960(원시 UI 문자열 테이블: 메인메뉴/스탯/아이템분류/세이브메시지) 추출.
#  슬롯은 재빌드해도 내용 불변, 위치만 이동 -> EBOOT 포인터로 슬롯시작 찾고 상대오프셋 기록.
#  제자리 교체(tbl_full_kr 인코딩, 널종료, avail 이내). 포인터 불변.
#  출력: work/menu_jp/menu_work.json  ([{roff, avail, jp, kr}, ...])
import json
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tjp = json.load(open("tbl_all.json", encoding="utf-8"))["TBL"]
PTR = 0x126F90
SLOT = 3960
# 슬롯 3960 내 클린 UI/메시지 구간 (상대오프셋). 앞쪽 바이너리 노이즈 회피.
REL_LO = 0xF000
REL_HI = 0x13200


def slot_start(dat_path, eboot_path):
    eb = open(eboot_path, "rb").read()
    dsz = os.path.getsize(dat_path)
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > dsz * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    return p[SLOT]


def decstr(dat, off, mx=220):
    s = ""
    i = off
    unk = 0
    while i < len(dat) - 1 and dat[i] != 0 and i < off + mx:
        c = dat[i]
        if c < 0x20:                 # 제어바이트(\x01 줄바꿈, \x0d\x0e KEY HELP 버튼코드 등) -> 태그
            s += "<%02X>" % c
            i += 1
            continue
        if c >= 0x81:
            v = Tjp.get("%04X" % ((c << 8) | dat[i + 1]))
            s += v if v else "?"
            unk += 0 if v else 1
            i += 2
        elif 0x20 <= c < 0x7f:
            s += chr(c)
            i += 1
        else:
            s += "#"
            unk += 1
            i += 1
    return s, i, unk


def avail(dat, off):
    i = off
    while dat[i] != 0:
        i += 2 if dat[i] >= 0x81 else 1
    e = i
    while e < len(dat) and dat[e] == 0:
        e += 1
    return e - off


def is_ui(s, unk):
    if unk:
        return False
    if len(s) < 2:
        return False
    jp = sum(1 for c in s if "぀" <= c <= "ヿ" or "一" <= c <= "鿿")
    return jp >= 1


def main():
    # jp 원문은 클린 백업(슬롯3960 미패치 상태)에서 읽는다. 없으면 최종본.
    srcp = "DAT_jp_final_preskit.BIN" if os.path.exists("DAT_jp_final_preskit.BIN") else "DAT_jp_final.BIN"
    dat = open(srcp, "rb").read()
    base = slot_start(srcp, "EBOOT_jp_new.BIN")
    LO, HI = base + REL_LO, base + REL_HI
    rows = []
    i = LO
    while i < HI:
        if dat[i] == 0:
            i += 1
            continue
        s, e, unk = decstr(dat, i)
        if is_ui(s, unk):
            rows.append({"roff": i - base, "avail": avail(dat, i), "jp": s, "kr": ""})
        i = e + 1
    out = "work/menu_jp/menu_work.json"
    if os.path.exists(out):
        old = {r["roff"]: r["kr"] for r in json.load(open(out, encoding="utf-8"))}
        for r in rows:
            if old.get(r["roff"]):
                r["kr"] = old[r["roff"]]
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    uniq = len({r["jp"] for r in rows})
    print(f"[OK] 슬롯{SLOT} 시작 {hex(base)} / UI 문자열 {len(rows)}개 (고유 {uniq}) -> {out}")


if __name__ == "__main__":
    main()
