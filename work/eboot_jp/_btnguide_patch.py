# -*- coding: utf-8 -*-
# 하단 버튼 가이드(選択/決定/キャンセル) 널채움+버튼코드밀림 교정 + 미번역 選択->선택 (2026-07-24).
#  ★증상: 씬 선택지 화면 하단이 KR 은 '선택' 1개만 표시(JP 는 選択/決定/キャンセル 3개).
#  ★원인: 취소(4B) 등이 짧아진 자리를 널로 채워 여분 널 + 버튼코드(<0d>XX)가 앞으로 밀림
#    -> 목록 파싱이 끊김(슬롯3960 KEY HELP 와 동일 패턴).
#  ★해법: 구간(953858~953940)을 원본 바이트로 통째 복원(버튼코드 위치/널구조 원상) 후,
#    각 텍스트 슬롯에만 kr+공백 채움(원문 슬롯길이 정확히, 널 금지, 버튼코드 불변).
#  ★選択 은 eboot_work 에 없던 미번역 -> '섬?' 깨짐 -> 여기서 선택 으로 채움.
#  사용: py work\eboot_jp\_btnguide_patch.py [--check]
import argparse
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
INV = {v: int(k, 16) for k, v in Tkr.items()}

REG_LO, REG_HI = 953858, 953940
# (off, kr) — 슬롯길이(jl)는 원본에서 '널 또는 버튼코드(0x0d) 중 먼저 오는 것'까지 자동산출.
#   선행 공백 유지(원문이 ' 決定' 처럼 공백시작).
ENTRIES = [
    (953865, " 다음"),    # 次へ
    (953877, " 선택"),    # 選択 (미번역이었음)
    (953889, " 결정"),    # 決定
    (953901, " 취소"),    # キャンセル
    (953921, " 선택"),    # 選択 (미번역이었음)
    (953933, " 결정"),    # 決定
]


def slot_len(orig, off):
    n = off
    while orig[n] != 0 and orig[n] != 0x0D:
        n += 1
    return n - off


def enc(s):
    o = bytearray()
    for c in s:
        o.append(0x20) if c == " " else o.extend(INV[c].to_bytes(2, "big"))
    return bytes(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()
    eb = bytearray(open(args.eboot, "rb").read())
    orig = open("ULJS00132_EBOOT.BIN", "rb").read()

    # 검증: 슬롯 = 원본에서 off 부터 '널까지'. 그 길이가 ENTRIES 의 jl 과 일치해야 함.
    bad = 0
    for off, kr in ENTRIES:
        jl = slot_len(orig, off)
        if len(enc(kr)) > jl:
            print(f"  [경고] off={off}: {kr!r} {len(enc(kr))}B > 슬롯 {jl}B 초과.")
            bad += 1
    if bad:
        print(f"[중단] 경고 {bad} — 기록 안 함.")
        return

    if not args.check:
        eb[REG_LO:REG_HI] = orig[REG_LO:REG_HI]      # 1) 구간 원본 복원
        for off, kr in ENTRIES:                      # 2) 텍스트만 공백채움 교체
            jl = slot_len(orig, off); b = enc(kr)
            eb[off:off + jl] = b + b"\x20" * (jl - len(b))
        open(args.eboot, "wb").write(bytes(eb))

    for off, kr in ENTRIES:
        jl = slot_len(orig, off)
        print(f"  off={off}: {kr!r} + 공백{jl-len(enc(kr))} (슬롯 {jl}B)")
    print(f"[{'검사' if args.check else '적용'}] 버튼가이드 {len(ENTRIES)}건 (구간 원본복원 + 공백채움, 버튼코드 불변)")
    if not args.check:
        print(f"[OK] {args.eboot} 버튼가이드 교정")


if __name__ == "__main__":
    main()
