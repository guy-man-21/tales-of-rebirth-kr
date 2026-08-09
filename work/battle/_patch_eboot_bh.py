import json, struct, re, sys, os
TAG=re.compile(r'<([0-9A-F]{4})>')
tbl=json.load(open('tbl_full_kr.json',encoding='utf-8'))['TBL']
inv={v:int(k,16) for k,v in tbl.items()}
def enc(kr):
    o=bytearray();i=0
    while i<len(kr):
        m=TAG.match(kr,i)
        if m:o+=struct.pack('>H',int(m.group(1),16));i=m.end();continue
        c=kr[i]
        if c in inv:o+=struct.pack('>H',inv[c]);i+=1;continue
        if ord(c)<0x80:o+=bytes([ord(c)]);i+=1;continue
        return None,c
    return bytes(o),None
apply='--apply' in sys.argv
ebp='EBOOT_cn_new.BIN'
for a in sys.argv[1:]:
    if a.startswith('--eboot='):ebp=a.split('=',1)[1]
src=ebp if (apply and os.path.exists(ebp)) else 'EBOOT_DEC.BIN'
eb=bytearray(open(src,'rb').read())
rows=json.load(open('work/battle/eboot_bh.json',encoding='utf-8'))
ok=over=err=0;probs=[]
for r in rows:
    kr=(r.get('kr') or '').strip()
    if not kr:continue
    e,bad=enc(kr)
    if e is None:err+=1;probs.append((hex(r['off']),f'인코딩 {bad!r}',kr));continue
    if len(e)+1>r['avail']:over+=1;probs.append((hex(r['off']),f'초과 {len(e)+1}>{r["avail"]}',kr));continue
    if apply:
        off=r['off'];eb[off:off+len(e)]=e
        for p in range(off+len(e),off+r['avail']):eb[p]=0
    ok+=1
print(f'[{"적용" if apply else "검사"}] OK {ok}/초과 {over}/에러 {err}')
for o,m,kr in probs[:20]:print(f'  {o}: {m} kr={kr!r}')
if apply and over==0 and err==0:
    open(ebp,'wb').write(eb);print(f'[OK] -> {ebp}')
