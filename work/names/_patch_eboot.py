#!/usr/bin/env python3
# EBOOT의 이름 테이블(화자 이름 해석용)을 한국어로 제자리 패치.
#  게임은 화자 이름을 DAT슬롯2가 아니라 EBOOT의 이름풀에서 해석함.
#  이름풀 = CN인코딩 가변길이 문자열 + 널패딩. 포인터참조라 시작오프셋 유지+널종료면 안전.
#  각 CN 이름바이트를 슬롯2 매핑으로 캐릭터 식별 -> 한국어. 다음 비널까지 공간 이내.
import json, struct, re, sys, os

TAG = re.compile(r'<([0-9A-F]{4})>')
tbl = json.load(open('tbl_full_kr.json', encoding='utf-8'))['TBL']
inv = {v: int(k, 16) for k, v in tbl.items()}
cn = open('DAT_cn.BIN', 'rb').read()

def encode(kr):
    out = bytearray(); i = 0
    while i < len(kr):
        m = TAG.match(kr, i)
        if m: out += struct.pack('>H', int(m.group(1), 16)); i = m.end(); continue
        c = kr[i]
        if c in inv: out += struct.pack('>H', inv[c]); i += 1; continue
        if ord(c) < 0x80: out += bytes([ord(c)]); i += 1; continue
        return None
    return bytes(out)

# 슬롯2 원본 CN 바이트 -> 한국어 (names_work.json의 kr)
def slot2_cn_bytes(off):
    e = off
    while cn[e] != 0: e += 1
    return cn[off:e]

work = json.load(open('work/names/names_work.json', encoding='utf-8'))
cnmap = {}   # cn_bytes -> kr
for r in work:
    kr = (r.get('kr') or '').strip()
    if not kr: continue
    b = slot2_cn_bytes(r['off'])
    if len(b) >= 2:            # 2바이트+ 이름만(오탐방지)
        cnmap[b] = kr

def main():
    apply = '--apply' in sys.argv
    ebp = 'EBOOT_cn_new.BIN'
    for a in sys.argv[1:]:
        if a.startswith('--eboot='): ebp = a.split('=', 1)[1]
    if apply and not os.path.exists(ebp):
        print(f'[!] {ebp} 없음'); return
    src = ebp if (apply and os.path.exists(ebp)) else 'EBOOT_DEC.BIN'
    eb = bytearray(open(src, 'rb').read())

    ok = over = 0; done = set(); rep = []
    for cnb, kr in sorted(cnmap.items(), key=lambda x: -len(x[0])):
        enc = encode(kr)
        if enc is None: continue
        start = 0
        while True:
            i = eb.find(cnb, start)
            if i < 0: break
            start = i + 1
            # 이 위치가 이름풀인지: 뒤에 널이 있고(엔트리 끝), 이름풀 영역(0xed000~0xef000 근처)
            if not (0xed000 <= i <= 0xef800): continue
            # 가용공간: cnb 끝부터 다음 비널까지
            e = i + len(cnb)
            while e < len(eb) and eb[e] == 0: e += 1
            avail = e - i            # 이 엔트리에 쓸 수 있는 총 바이트(다음 이름 시작 전까지)
            if len(enc) + 1 > avail:
                over += 1; rep.append((hex(i), f'초과 {len(enc)+1}>{avail}', kr)); continue
            if apply:
                eb[i:i + len(enc)] = enc
                for p in range(i + len(enc), i + avail): eb[p] = 0
            ok += 1; done.add(kr)
    print(f'[{"적용" if apply else "검사"}] 패치 {ok}곳 / 초과 {over} / 매칭이름 {len(done)}종')
    for o, m, kr in rep[:20]: print(f'  {o}: {m} kr={kr!r}')
    if apply and over == 0:
        open(ebp, 'wb').write(eb)
        print(f'[OK] EBOOT 패치 -> {ebp}')

if __name__ == '__main__':
    main()
