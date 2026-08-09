#!/usr/bin/env python3
# 이름 테이블(슬롯 2, 16바이트 고정 엔트리) JP원문+CN오프셋 추출.
import json, struct, os

def rp(eb, ds, pb=0x126F90):
    e = open(eb, 'rb').read(); p = []; i = 0
    while True:
        o = pb + i * 4
        if o + 4 > len(e): break
        v = struct.unpack_from("<I", e, o)[0]
        if i > 0 and (v < p[-1] or v > ds * 1.05): break
        p.append(v); i += 1
        if i > 40000: break
    return p

Tjp = json.load(open('tbl_all.json', encoding='utf-8')); Tjp = Tjp.get('TBL', Tjp)
Tcn = json.load(open('tbl_full_kr.json', encoding='utf-8'))['TBL']
jp = open('DAT.BIN', 'rb').read(); jpp = rp('ULJS00132_EBOOT.BIN', len(jp))
cn = open('DAT_cn.BIN', 'rb').read(); cnp = rp('EBOOT_DEC.BIN', len(cn))

ENTRY = 16
BASE = 0xe93c8          # 이름테이블 시작(JP·CN 동일 절대오프셋; 슬롯2 정렬)
N = 260                 # 넉넉히 스캔

def decode(d, off, T, mb=ENTRY):
    s = ''; i = off
    while i < off + mb:
        b = d[i]
        if b == 0: break
        if b >= 0x81 and i + 1 < off + mb:
            code = (b << 8) | d[i + 1]; v = T.get(f'{code:04X}')
            s += v if v else f'<{code:04X}>'; i += 2
        else:
            s += chr(b); i += 1
    return s

rows = []
for k in range(N):
    off = BASE + k * ENTRY
    jt = decode(jp, off, Tjp)
    ct = decode(cn, off, Tcn)
    rows.append({'idx': k, 'off': off, 'jp': jt, 'cn_garbled': ct, 'kr': ''})
json.dump(rows, open('work/names/names_work.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
non_empty = sum(1 for r in rows if r['jp'].strip())
print(f'엔트리 {N}개 (비어있지않음 {non_empty}) -> names_work.json')
for r in rows:
    if r['jp'].strip():
        print(f"  [{r['idx']:3}] {r['jp'][:22]!r}")
