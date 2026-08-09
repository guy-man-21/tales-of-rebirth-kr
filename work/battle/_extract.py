#!/usr/bin/env python3
# 슬롯 15900(battle help/전투 텍스트) JP(원문)+CN(오프셋) 문자열 추출·순서매칭.
import json, struct

def read_pointers(eboot_path, dat_size, ptr_base=0x126F90):
    eboot = open(eboot_path, 'rb').read(); ptrs = []; i = 0
    while True:
        off = ptr_base + i * 4
        if off + 4 > len(eboot): break
        v = struct.unpack_from("<I", eboot, off)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size * 1.05): break
        ptrs.append(v); i += 1
        if i > 40000: break
    return ptrs

Tjp = json.load(open('tbl_all.json', encoding='utf-8')); Tjp = Tjp.get('TBL', Tjp)
Tcn = json.load(open('tbl_full_kr.json', encoding='utf-8'))['TBL']
SLOT = 15900

def load(datp, ebootp):
    d = open(datp, 'rb').read(); p = read_pointers(ebootp, len(d)); return d, p

def is_text(v):
    return ('가' <= v <= '힣' or '぀' <= v <= 'ヿ' or '一' <= v <= '鿿'
            or 0x3000 <= ord(v) < 0x3100)

def strings(d, a, b, T):
    out = []; i = a
    while i < b - 1:
        if d[i] == 0 and d[i + 1] == 0:
            i += 2; continue
        s = ''; j = i; binc = 0; txtc = 0
        while j < b - 1:
            code = (d[j] << 8) | d[j + 1]
            if code == 0: break
            v = T.get(f'{code:04X}')
            if v:
                s += v
                if is_text(v): txtc += 1
                else: binc += 1
            else:
                s += f'<{code:04X}>'; binc += 1
            j += 2
        out.append((i, j - i, s, txtc, binc))
        i = j + 2
    return out

jp, jpp = load('DAT.BIN', 'ULJS00132_EBOOT.BIN')
cn, cnp = load('DAT_cn.BIN', 'EBOOT_DEC.BIN')
js = [x for x in strings(jp, jpp[SLOT], jpp[SLOT + 1], Tjp) if x[3] >= 3 and x[4] <= x[3]]
cs = [x for x in strings(cn, cnp[SLOT], cnp[SLOT + 1], Tcn) if x[3] >= 3 and x[4] <= x[3]]
print(f'JP 텍스트문자열 {len(js)}개, CN {len(cs)}개')

rows = []
for k in range(min(len(js), len(cs))):
    jo, jl, jt, _, _ = js[k]; co, cl, ct, _, _ = cs[k]
    rows.append({'idx': k, 'cn_off': co, 'cn_len': cl, 'jp': jt, 'cn_garbled': ct})
json.dump(rows, open('work/battle/battle_strings.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('저장 work/battle/battle_strings.json')
print('=== 샘플 (idx | CN바이트길이 | JP원문) ===')
for r in rows[:40]:
    print(f'  #{r["idx"]:3} len{r["cn_len"]:3}: {r["jp"][:46]!r}')
