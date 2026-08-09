#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_global_hangul.py — 전역 한글 코드체계 생성 (옵션1: 상용 2350 일괄)

code_index_map.json 의 game_index>=200 한자를 회수 슬롯으로 삼아,
KS X 1001 상용 2350 음절을 결정론적으로 일괄 배정한다.
한 번 생성하면 모든 씬이 이 매핑 하나를 참조 (인코딩 SoT).

배정 원칙:
  - 희생 후보: game_index>=min_index 인 CJK 한자 (font_insert -96 보정 통과)
  - game_index 오름차순 정렬 → 음절과 순서대로 1:1 (결정론적, 재현가능)
  - 음절 순서: KS X 1001 완성형 순서(가나다순 유사)

출력:
  tbl_full_kr.json    : tbl_all 구조 + TBL에 회수코드가 한글로 교체된 것 (삽입기용)
  hangul_font_map.txt : "game_index:음절,..." 전체 (폰트 빌더용)
  hangul_reclaim.json : {음절: {text_code, game_index, sacrificed}} 전체 SoT
  hangul_syllables.txt : 배정된 음절 목록(순서대로)

사용:
  py build_global_hangul.py --map code_index_map.json --tbl tbl_all.json
  py build_global_hangul.py --map code_index_map.json --tbl tbl_all.json --count 2350 --min-index 200
"""
import argparse
import json
import sys


def ksx1001_syllables():
    """KS X 1001 완성형 2350 음절을 순서대로 생성.
    EUC-KR(cp949 하위집합) 0xB0A1~0xC8FE 영역에서 유효한 완성형만."""
    out = []
    for lead in range(0xB0, 0xC9):
        for trail in range(0xA1, 0xFF):
            try:
                ch = bytes([lead, trail]).decode('euc-kr')
                if 0xAC00 <= ord(ch) <= 0xD7A3:  # 한글 음절만
                    out.append(ch)
            except Exception:
                pass
    return out


def is_cjk(ch):
    return 0x4E00 <= ord(ch) <= 0x9FFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', required=True, help='code_index_map.json')
    ap.add_argument('--tbl', required=True, help='tbl_all.json (원본; 회수 미적용)')
    ap.add_argument('--count', type=int, default=2350, help='배정할 음절 수(기본 2350)')
    ap.add_argument('--min-index', type=int, default=200)
    ap.add_argument('--out-prefix', default='')
    args = ap.parse_args()

    code_map = json.load(open(args.map, encoding='utf-8'))
    syllables = ksx1001_syllables()[:args.count]
    print(f"[i] 상용 음절 {len(syllables)}개 (앞: {''.join(syllables[:10])} ...)")

    # 희생 후보: game_index>=min, CJK, game_index 오름차순
    pool = [c for c in code_map
            if is_cjk(c) and code_map[c]['game_index'] >= args.min_index]
    pool.sort(key=lambda c: code_map[c]['game_index'])
    print(f"[i] 회수 후보 한자(game_index>={args.min_index}): {len(pool)}개")

    if len(pool) < len(syllables):
        print(f"[!] 후보({len(pool)}) < 음절({len(syllables)}). --min-index 낮추거나 --count 줄이기",
              file=sys.stderr)
        sys.exit(1)

    # 결정론적 1:1 배정
    reclaim = {}      # 음절 -> {text_code, game_index, sacrificed}
    tbl_patch = {}    # text_code -> 음절
    font_pairs = []   # game_index:음절
    for syl, victim in zip(syllables, pool):
        info = code_map[victim]
        reclaim[syl] = {'text_code': info['text_code'],
                        'game_index': info['game_index'],
                        'sacrificed': victim}
        tbl_patch[info['text_code']] = syl
        font_pairs.append(f"{info['game_index']}:{syl}")

    pfx = args.out_prefix

    # tbl_full_kr.json : tbl_all 로드 후 TBL에 회수코드 교체
    tbl = json.load(open(args.tbl, encoding='utf-8'))
    if 'TBL' not in tbl:
        print("[!] tbl에 TBL 그룹 없음", file=sys.stderr); sys.exit(1)
    keymap = {k.upper(): k for k in tbl['TBL']}
    replaced = 0
    for code, syl in tbl_patch.items():
        realk = keymap.get(code.upper(), code)
        tbl['TBL'][realk] = syl
        replaced += 1
    json.dump(tbl, open(pfx+'tbl_full_kr.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    json.dump(reclaim, open(pfx+'hangul_reclaim.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    open(pfx+'hangul_font_map.txt', 'w', encoding='utf-8').write(",".join(font_pairs))
    open(pfx+'hangul_syllables.txt', 'w', encoding='utf-8').write("".join(syllables))

    print(f"\n[✓] 전역 한글 코드체계 생성 완료")
    print(f"    tbl_full_kr.json     : TBL {replaced}개 코드 → 한글 (삽입기용 SoT)")
    print(f"    hangul_reclaim.json  : 음절↔코드 전체 매핑")
    print(f"    hangul_font_map.txt  : 폰트 빌더용 {len(font_pairs)}쌍")
    print(f"    hangul_syllables.txt : 배정 음절 목록")
    print(f"\n[i] game_index 범위: {reclaim[syllables[0]]['game_index']} ~ {reclaim[syllables[-1]]['game_index']}")
    print(f"[i] 예시 배정:")
    for syl in ['가', '누', '구', '한', '글'][:5]:
        if syl in reclaim:
            r = reclaim[syl]
            print(f"    {syl} ← {r['sacrificed']} [code {r['text_code']} / gi {r['game_index']}]")


if __name__ == '__main__':
    main()
