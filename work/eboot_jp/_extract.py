#!/usr/bin/env python3
# JP EBOOT 평문 텍스트(메뉴버튼/스킷제목/화자이름/네비힌트/아이템·몬스터명) 추출.
#  게임이 ULJS00132_EBOOT.BIN 복사본으로 표시. 제자리 교체(회수 인코딩, 널종료, 포인터불변).
#  avail = 문자열 끝 ~ 다음 비널 시작까지(=이 엔트리에 쓸 수 있는 총 바이트, 널 포함).
#  출력: work/eboot_jp/eboot_work.json  ([{off,avail,jp,kr,cat}, ...])
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tjp = json.load(open("tbl_all.json", encoding="utf-8"))
Tjp = Tjp.get("TBL", Tjp)
eb = open("ULJS00132_EBOOT.BIN", "rb").read()

# 평문 텍스트 밀집 구간 (스캔으로 확인). 코드영역 노이즈 회피 위해 좁게 잡음.
RANGES = [
    (0x0E8A00, 0x0E8E60, "menu"),    # 메뉴/필드 동작 버튼 (入る/次へ/決定...)
    (0x0E9C00, 0x0EB100, "skit"),    # 스킷 제목 (のバトルブック・１ 등, 이름 런타임접두)
    (0x0EB100, 0x0EB600, "skill"),   # 특기 변화 설명
    (0x0EDEB0, 0x0EDF58, "name"),    # 화자 이름 풀 (ヴェイグ~リンドブロム 15개, 뒤는 영문 디버그)
    (0x0EF700, 0x0EFF00, "nav"),     # 네비/목표 힌트 (「急がば山へ」 등)
    (0x0EFF00, 0x118200, "title"),   # 스킷 제목바 + 목표힌트(「」형 979) + 등급상점/NG+ UI
]


def decstr(off):
    s = ""
    i = off
    unk = 0
    while i < len(eb) - 1:
        c = eb[i]
        if c == 0:
            break
        if c >= 0x81:
            code = (c << 8) | eb[i + 1]
            v = Tjp.get(f"{code:04X}")
            if v:
                s += v
            else:
                s += "?"
                unk += 1
            i += 2
        elif 0x20 <= c < 0x7f:
            s += chr(c)
            i += 1
        else:
            s += "?"
            unk += 1
            i += 1
    return s, i, unk


def is_clean(s, unk):
    jp = sum(1 for c in s if "぀" <= c <= "ヿ" or "一" <= c <= "鿿" or c in "・ー")
    return unk == 0 and jp >= 1 and len(s) >= 1


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
    for LO, HI, cat in RANGES:
        i = LO
        while i < HI:
            if eb[i] == 0:
                i += 1
                continue
            s, e, unk = decstr(i)
            if is_clean(s, unk):
                rows.append({"off": i, "avail": avail(i), "jp": s, "kr": "", "cat": cat})
            i = e + 1
    out = "work/eboot_jp/eboot_work.json"
    # 기존 kr 보존
    if os.path.exists(out):
        old = {r["off"]: r["kr"] for r in json.load(open(out, encoding="utf-8"))}
        for r in rows:
            if old.get(r["off"]):
                r["kr"] = old[r["off"]]
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    cc = Counter(r["cat"] for r in rows)
    print(f"추출 {len(rows)}개 -> {out}")
    for c, n in cc.items():
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
