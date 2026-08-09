# -*- coding: utf-8 -*-
# 기술 발음표기(가타카나 후리가나) 슬롯 비우기. 한자명 뒤에 붙던 음차/중복 발음을 공백으로 채워
#  화면엔 한글 기술명만 1회 표시되게 함. EBOOT_jp_new.BIN 의 해당 슬롯만 제자리(공백채움, 널보존).
#  ★대상 = 순수한자명(≤8, 한자/・만) 바로 뒤의 가타카나 슬롯 + off>=MIN_OFF(스킬테이블 시작).
#    앞쪽 인명(휴마/긴나르/크로넬 등)은 MIN_OFF 미만이라 제외됨.
#  사용: py work\eboot_jp\_blank_readings.py --check   # 대상 목록만
#        py work\eboot_jp\_blank_readings.py           # 적용
import argparse
import json
import os
import re

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MIN_OFF = 1026924   # 베이그 스킬테이블 시작 (이 앞은 인명/타이틀 = 제외)
MAX_OFF = 1037000   # 스킬명 테이블 끝 (1036580) 직후. 이 뒤는 지명/음식/빈칸 오탐 = 제외
KATA = re.compile(r'^[ァ-ヶ・ー]+$')
PURE = re.compile(r'^[一-鿿・]{1,8}$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()

    d = json.load(open("work/eboot_jp/eboot_work.json", encoding="utf-8"))
    rows = sorted((d if isinstance(d, list) else d.get("rows", d.get("lines", []))),
                  key=lambda r: r.get("off") or 0)
    orig = open("ULJS00132_EBOOT.BIN", "rb").read()   # jplen(발음 원본 길이) 기준
    eb = bytearray(open(args.eboot, "rb").read())

    targets = []
    for i in range(1, len(rows)):
        jp = rows[i].get("jp") or ""
        pjp = rows[i - 1].get("jp") or ""
        off = rows[i].get("off") or 0
        gap = off - (rows[i - 1].get("off") or 0)
        if MIN_OFF <= off < MAX_OFF and KATA.match(jp) and PURE.match(pjp) and 4 < gap <= 16:
            # budget = 원본 발음 바이트수 (널까지)
            e = off
            while e < len(orig) and orig[e] != 0:
                e += 1
            targets.append((off, e - off, rows[i - 1].get("kr"), rows[i].get("kr")))

    print(f"[{'검사' if args.check else '적용'}] 발음슬롯 비우기 대상 {len(targets)}개")
    for off, budget, name, rd in targets[:12]:
        print(f"  off={off} budget={budget}  기술 {name!r}  발음 {rd!r} -> (공백)")
    if len(targets) > 12:
        print(f"  ... 외 {len(targets)-12}개")

    if not args.check:
        for off, budget, _, _ in targets:
            eb[off:off + budget] = b" " * budget
        open(args.eboot, "wb").write(bytes(eb))
        print(f"[OK] {args.eboot} 발음슬롯 {len(targets)}개 공백처리 (크기·널구조 불변)")


if __name__ == "__main__":
    main()
