#!/usr/bin/env python3
# 이름 테이블(슬롯2, 16바이트 고정 엔트리) 제자리 패치.
#  kr 인코딩(가변길이: 한글/CJK/전각=2B, ASCII=1B, <XXXX>=2B) <=15바이트 + 널패딩(16B).
import json, struct, re, sys, os

ENTRY = 16
TAG = re.compile(r'<([0-9A-F]{4})>')
tbl = json.load(open('tbl_full_kr.json', encoding='utf-8'))['TBL']
inv = {v: int(k, 16) for k, v in tbl.items()}

def encode(kr):
    out = bytearray(); i = 0
    while i < len(kr):
        m = TAG.match(kr, i)
        if m:
            out += struct.pack('>H', int(m.group(1), 16)); i = m.end(); continue
        c = kr[i]
        if c in inv:
            out += struct.pack('>H', inv[c]); i += 1; continue
        if ord(c) < 0x80:
            out += bytes([ord(c)]); i += 1; continue
        return None, c
    return bytes(out), None

def main():
    dat_path = 'DAT_cn_new.BIN'
    for a in sys.argv[1:]:
        if a.startswith('--dat='): dat_path = a.split('=', 1)[1]
    apply = '--apply' in sys.argv
    rows = json.load(open('work/names/names_work.json', encoding='utf-8'))
    if apply and not os.path.exists(dat_path):
        print(f'[!] {dat_path} 없음'); return
    data = bytearray(open(dat_path, 'rb').read()) if apply else None
    ok = skip = over = err = 0; probs = []
    for r in rows:
        kr = (r.get('kr') or '').strip()
        if not kr: skip += 1; continue
        enc, bad = encode(kr)
        if enc is None:
            err += 1; probs.append((r['idx'], f'인코딩불가 {bad!r}', kr)); continue
        if len(enc) > ENTRY - 1:
            over += 1; probs.append((r['idx'], f'초과 {len(enc)}>{ENTRY-1}B', kr)); continue
        if apply:
            off = r['off']
            data[off:off + ENTRY] = enc + b'\x00' * (ENTRY - len(enc))
        ok += 1
    print(f'[{"적용" if apply else "검사"}] OK {ok} / 스킵 {skip} / 초과 {over} / 에러 {err}')
    for idx, m, kr in probs[:30]:
        print(f'  [{idx}] {m}  kr={kr!r}')
    if apply and over == 0 and err == 0:
        open(dat_path, 'wb').write(data)
        print(f'[OK] 패치 -> {dat_path}')

if __name__ == '__main__':
    main()
