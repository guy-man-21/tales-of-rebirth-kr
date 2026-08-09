#!/usr/bin/env python3
# battle_strings.json -> 번역 작업목록. 각 문자열의 인라인 태그 보존 + 글자예산 계산.
#  글자예산 max_units = cn_len/2 (2바이트/유닛). 태그<XXXX>도 1유닛. 번역은 태그 유지하고
#  한글+공백+기존태그 합쳐 max_units 이내.
import json, re
TAG = re.compile(r'<[0-9A-F]{4}>')
rows = json.load(open('work/battle/battle_strings.json', encoding='utf-8'))
DEBUG_KEYS = ['デバッグ', 'ﾃﾞﾊﾞｯｸﾞ', 'debug', 'テスト', '←', 'ＦＲＴ', 'ajstep']
work = []
for r in rows:
    jp = r['jp']
    core = TAG.sub('', jp)
    has_jp = any('぀' <= c <= 'ヿ' or '一' <= c <= '鿿' for c in core)
    if not has_jp or len(core) < 2:
        continue
    tags = TAG.findall(jp)
    if len(tags) > 3:  # 바이너리 잔재 많은 건 제외(안전)
        continue
    is_debug = any(k in jp for k in DEBUG_KEYS)
    work.append({
        'idx': r['idx'], 'cn_off': r['cn_off'], 'cn_len': r['cn_len'],
        'max_units': r['cn_len'] // 2,
        'jp': jp, 'debug': is_debug, 'kr': ''
    })
json.dump(work, open('work/battle/battle_work.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
nd = sum(1 for w in work if not w['debug'])
print(f'작업목록 {len(work)}개 (플레이어노출 {nd}, 디버그 {len(work)-nd}) -> battle_work.json')
print('=== 플레이어노출 대상 (idx | 예산유닛 | jp) ===')
for w in work:
    if not w['debug']:
        print(f'  #{w["idx"]:3} u{w["max_units"]:2}: {w["jp"][:48]!r}')
