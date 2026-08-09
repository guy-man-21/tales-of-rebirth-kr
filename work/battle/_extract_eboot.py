#!/usr/bin/env python3
# EBOOT의 battle help/상태효과 텍스트 블록 추출 (JP원문 + CN오프셋/여유공간).
#  게임이 이 EBOOT 복사본으로 표시함(슬롯15900 아님).
#  CN 버전은 전각공백 패딩 있어 여유공간 = 다음 비널 문자열 시작까지.
import json
Tjp = json.load(open('tbl_all.json', encoding='utf-8')); Tjp = Tjp.get('TBL', Tjp)
Tcn = json.load(open('tbl_full_kr.json', encoding='utf-8'))['TBL']
jpeb = open('ULJS00132_EBOOT.BIN', 'rb').read()
cneb = open('EBOOT_DEC.BIN', 'rb').read()

# battle help + 상태효과 영역
RANGES = [(0x105720,0x105f00),(0x10feb4,0x10ffa0)]

def decstr(d, off, T):
    s = ''; i = off
    while i < len(d) - 1:
        c = d[i]
        if c == 0: break
        if c >= 0x81:
            code = (c << 8) | d[i + 1]; v = T.get(f'{code:04X}')
            s += v if v else f'<{code:04X}>'; i += 2
        else:
            s += chr(c); i += 1
    return s, i

def avail(d, off):
    # off의 문자열 끝~다음 비널 시작까지 = 이 엔트리에 쓸 수 있는 총 바이트
    i = off
    while d[i] != 0: i += (2 if d[i] >= 0x81 else 1)
    e = i
    while e < len(d) and d[e] == 0: e += 1
    return e - off

rows = []
for LO, HI in RANGES:
  i = LO
  while i < HI:
    if jpeb[i] == 0: i += 1; continue
    js, jni = decstr(jpeb, i, Tjp)
    jhas = any('぀' <= c <= 'ヿ' or '一' <= c <= '鿿' for c in js)
    if jhas and len(js) >= 2:
        rows.append({'off': i, 'avail': avail(cneb, i), 'jp': js,
                     'cn': decstr(cneb, i, Tcn)[0], 'kr': ''})
    i = jni + 1
json.dump(rows, open('work/battle/eboot_bh.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(f'EBOOT battle 텍스트 {len(rows)}개 -> eboot_bh.json')
for r in rows:
    print(f"  {hex(r['off'])} (여유{r['avail']}B): {r['jp'][:36]!r}")
