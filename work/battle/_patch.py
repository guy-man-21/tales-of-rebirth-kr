#!/usr/bin/env python3
# battle_work.json(kr 채움)을 슬롯 15900에 제자리 패치.
#  - kr을 tbl_full_kr 코드로 인코딩(태그 <XXXX>는 그 코드값 그대로 2바이트).
#  - 원본 CN 바이트길이(cn_len) 이내여야 함(널종료). 넘치면 에러 리포트.
#  - 대상 DAT: 기본 DAT_cn_new.BIN(빌드 산출물). 없으면 --dat 로 지정.
#  슬롯 15900은 build_dat가 안 건드리므로 오프셋(cn_off)이 그대로 유효.
import json, struct, re, sys, shutil, os

TAG = re.compile(r'<([0-9A-F]{4})>')
tbl = json.load(open('tbl_full_kr.json', encoding='utf-8'))['TBL']
inv = {v: int(k, 16) for k, v in tbl.items()}

def encode(kr):
    """kr -> 바이트열. 가변길이: 한글/CJK=2바이트(tbl코드), ASCII(<0x80)=1바이트,
    <XXXX> 태그=그 2바이트값 그대로. 실패시 (None, 문제문자)."""
    out = bytearray()
    i = 0
    while i < len(kr):
        m = TAG.match(kr, i)
        if m:
            out += struct.pack('>H', int(m.group(1), 16)); i = m.end(); continue
        c = kr[i]
        if c in inv:
            out += struct.pack('>H', inv[c]); i += 1; continue
        if ord(c) < 0x80:            # ASCII (공백/기호/숫자/영문) = 1바이트
            out += bytes([ord(c)]); i += 1; continue
        return None, c
    return bytes(out), None

def main():
    dat_path = 'DAT_cn_new.BIN'
    for a in sys.argv[1:]:
        if a.startswith('--dat='):
            dat_path = a.split('=', 1)[1]
    apply = '--apply' in sys.argv
    work = json.load(open('work/battle/battle_work.json', encoding='utf-8'))

    if apply and not os.path.exists(dat_path):
        print(f'[!] {dat_path} 없음. 먼저 build_dat 로 생성하거나 --dat= 지정')
        return
    data = bytearray(open(dat_path, 'rb').read()) if apply else None

    ok = skip = overflow = enc_err = 0
    problems = []
    for w in work:
        kr = (w.get('kr') or '').strip()
        if not kr:
            skip += 1; continue
        enc, bad = encode(kr)
        if enc is None:
            enc_err += 1; problems.append((w['idx'], f'인코딩불가 {bad!r}', kr)); continue
        nbytes = len(enc)
        if nbytes > w['cn_len']:
            overflow += 1
            problems.append((w['idx'], f'초과 {nbytes}>{w["cn_len"]}B', kr)); continue
        if apply:
            off = w['cn_off']
            data[off:off + nbytes] = enc
            # 널 종료 + 남는 원본자리 널패딩
            for p in range(off + nbytes, off + w['cn_len']):
                data[p] = 0
        ok += 1

    print(f'[{"적용" if apply else "검사"}] OK {ok} / 스킵(빈칸) {skip} / 초과 {overflow} / 인코딩에러 {enc_err}')
    for idx, msg, kr in problems[:40]:
        print(f'  #{idx}: {msg}  kr={kr[:30]!r}')
    if apply and overflow == 0 and enc_err == 0:
        out = dat_path if '--inplace' in sys.argv else dat_path.replace('.BIN', '_btl.BIN')
        open(out, 'wb').write(data)
        print(f'[OK] 패치 저장 -> {out}')

if __name__ == '__main__':
    main()
