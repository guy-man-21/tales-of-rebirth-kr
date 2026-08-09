# -*- coding: utf-8 -*-
# 작전행동 이름(19개) 전용 편집/패치 도구. EBOOT_jp_new.BIN 의 해당 오프셋만 제자리 교체.
#  ★다른 번역(태그공백 교정 등)에 영향 없음. SoT = work/eboot_jp/strat_names.json 의 "kr" 필드.
#  budget(=원문 바이트수) 초과 시 적용 안 하고 경고만 출력 -> 문구를 줄여야 함.
#  한글=2B, 영문/공백/반각숫자=1B, 전각(１・ 등)=2B.
#
#  사용법:
#    py work\eboot_jp\_strat_patch.py --check     # 검증만 (길이 확인, 기록 안 함)
#    py work\eboot_jp\_strat_patch.py             # EBOOT_jp_new.BIN 에 적용 + cbatch 동기화
#  적용 후 롬 배치: EBOOT_jp_new.BIN 을 롬의 EBOOT 위치로 copy (또는 change_file_nb_JP.bat).
import argparse
import json
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}


def enc(kr):
    """kr -> bytes. 인코딩 불가 문자가 있으면 (None, 그 문자)."""
    o = bytearray()
    for c in kr:
        if ord(c) < 0x80:
            o.append(ord(c))
        elif c in inv:
            o += struct.pack(">H", inv[c])
        else:
            return None, c
    return bytes(o), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="검증만 (기록 안 함)")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    args = ap.parse_args()

    rows = json.load(open("work/eboot_jp/strat_names.json", encoding="utf-8"))
    eb = bytearray(open(args.eboot, "rb").read())

    ok = 0
    problems = []
    for r in rows:
        off, budget, kr = r["off"], r["budget"], (r.get("kr") or "")
        e, bad = enc(kr)
        if e is None:
            problems.append(f"  off={off}: 폰트에 없는 문자 {bad!r}  ({kr!r})")
            continue
        if len(e) > budget:
            problems.append(f"  off={off}: {len(e)}B > 예산 {budget}B (+{len(e)-budget})  ({kr!r})")
            continue
        # 예산 딱 맞게 뒤 공백 채움 (널 위치 보존)
        filled = e + b" " * (budget - len(e))
        if not args.check:
            eb[off:off + budget] = filled
        ok += 1

    if problems:
        print(f"[문제 {len(problems)}건 — 적용 안 됨, 문구를 줄이세요]:")
        for p in problems:
            print(p)
    print(f"[{'검사' if args.check else '적용'}] 정상 {ok} / 문제 {len(problems)} (총 {len(rows)})")

    if not args.check and ok and not problems:
        open(args.eboot, "wb").write(bytes(eb))
        print(f"[OK] {args.eboot} 작전행동 {ok}개 적용")
        # cbatch 동기화 (전체 재빌드 시 일관성 유지)
        cb_path = "work/eboot_jp/cbatch_008_kr.json"
        cb = json.load(open(cb_path, encoding="utf-8"))
        cbrows = cb if isinstance(cb, list) else cb.get("lines", [])
        krmap = {r["off"]: r.get("kr") for r in rows}
        n = 0
        for cr in cbrows:
            if cr.get("off") in krmap:
                cr["kr"] = krmap[cr["off"]]
                n += 1
        json.dump(cb, open(cb_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[OK] cbatch_008_kr.json {n}개 동기화 (전체 재빌드 대비)")
    elif not args.check and problems:
        print("[중단] 문제 항목이 있어 기록하지 않았습니다. 위 항목 문구를 줄인 뒤 다시 실행하세요.")


if __name__ == "__main__":
    main()
