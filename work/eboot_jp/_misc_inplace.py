# -*- coding: utf-8 -*-
# EBOOT 단발 제자리 수정 모음 (2026-07-24~). 추출기가 놓친 미번역/오타 등 소규모 픽스.
#  각 항목: (off, 원문검증바이트(원본EBOOT기준 hex), 새 kr) - 같은 길이 제자리 교체만.
#  idempotent: 현재 바이트가 이미 kr 이면 스킵, 원문도 kr 도 아니면 경고(다른 패치와 충돌 감지).
#  사용: py work\eboot_jp\_misc_inplace.py [--check]
import argparse
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
INV = {v: int(k, 16) for k, v in Tkr.items()}


def enc(s):
    o = bytearray()
    for c in s:
        if c == " ":
            o.append(0x20)
        else:
            o += INV[c].to_bytes(2, "big")
    return bytes(o)


# (off, 원문 hex, 새 kr) — 반드시 len(enc(kr)) == len(원문바이트)
FIXES = [
    # 지형 라벨 草原 -> 초원 (필드 미니맵 헤더 '：草原' = '즐막'으로 깨져 보이던 것.
    #  엔트리 앞 바이너리 프리픽스 때문에 추출기가 스킵했던 미번역. 2026-07-24)
    (1089510, "e4c69fe5", "초원"),
    # 발견물/칭호/용어 4B 동일길이 (2026-07-25 사냥분)
    (1080544, "eaef9dd9", "용권"),
    (1081956, "eae8e893", "유빙"),
    (1082372, "9cc4e042", "염호"),
    (1082624, "9cd7e0ed", "황사"),
    (1084100, "e26ee893", "수빙"),
    (1087604, "9c80e5e1", "와류"),
    (1100432, "e5c0e398", "충신"),
    (1113408, "e3ade2a5", "진술"),
    (1113532, "eb80e2a5", "연술"),
    (1114264, "eb7e9f99", "연계"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()
    eb = bytearray(open(args.eboot, "rb").read())

    ok = skip = warn = 0
    for off, jphex, kr in FIXES:
        jp = bytes.fromhex(jphex)
        b = enc(kr)
        assert len(b) == len(jp), (off, kr)
        cur = bytes(eb[off:off + len(jp)])
        if cur == b:
            skip += 1          # 이미 적용
            continue
        if cur != jp:
            print(f"  [경고] off={off}: 현재바이트 {cur.hex()} != 원문 {jphex}. 스킵.")
            warn += 1
            continue
        if not args.check:
            eb[off:off + len(b)] = b
        ok += 1
        print(f"  off={off}: -> {kr!r}")
    print(f"[{'검사' if args.check else '적용'}] {ok}건 / 기적용 {skip} / 경고 {warn}")
    if not args.check and ok:
        open(args.eboot, "wb").write(bytes(eb))
        print(f"[OK] {args.eboot} 단발수정")


if __name__ == "__main__":
    main()
