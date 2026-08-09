# -*- coding: utf-8 -*-
# 씬 서수 진단 (2026-08-02 전수감사 도구): JP(DAT.BIN) vs KR(DAT_jp_final.BIN)
# 태그인식 문자열 워크 수 + select/notice 서수 비교 + 불일치 시 주변 문자열 덤프.
# 사용: py work\speakers_jp\_ordcheck.py [씬번호...]  (무인자 = 정기선 씬 8곳)
# 씬 재빌드 후 회귀검사 표준 도구. 전수 검사는 씬 목록을 인자로 나열.
import os, sys, json, struct
os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib"); sys.path.insert(0, ".")
from pathlib import Path
from pythonlib.formats.rebirth.scpk import Scpk
from pythonlib.formats.rebirth.theirsce import Theirsce
from pythonlib.utils import comptolib
from story_pipeline_bin import make_mini
from build_all_jp import parse_blobs

SCENES = [int(a) for a in sys.argv[1:] if a.isdigit()] or [4201,4270,4339,4565,4606,4619,5167,5172]

def rp(buf, ds):
    p=[];k=0
    while True:
        v=struct.unpack_from("<I",buf,0x126F90+k*4)[0]
        if k>0 and (v<p[-1] or v>ds*1.05): break
        p.append(v);k+=1
        if k>40000: break
    return p

src=open("DAT.BIN","rb").read()
sp_=rp(open("ULJS00132_EBOOT.BIN","rb").read(),len(src))
dat=open("DAT_jp_final.BIN","rb").read()
dp=rp(open("EBOOT_jp_new.BIN","rb").read(),len(dat))
mini_ex=make_mini("tbl_all.json")
mini_kr=make_mini("tbl_full_kr.json")

def get_rsce(buf, ptrs, sc):
    p0=ptrs[sc]; base=buf.rfind(b"SCPK",max(0,p0-64),p0+8)
    if base<0: return None,None
    nf=struct.unpack_from("<I",buf,base+8)[0]
    sizes=[struct.unpack_from("<I",buf,base+16+4*k)[0] for k in range(nf)]
    cont=bytes(buf[base:base+16+4*nf+sum(sizes)])
    blobs=parse_blobs(cont)
    _,off,size,idx=next(bb for bb in blobs if bb[0]=="sce")
    blob=cont[off:off+size]
    rsce=comptolib.decompress_data(blob)
    return rsce,cont

def walk(rsce, mini):
    tio=Theirsce(rsce); so=tio.strings_offset
    strs=[]; q=so
    while q<len(rsce):
        if rsce[q]==0:
            q+=1;continue
        st=q
        try:
            txt=mini.bytes_to_text(tio,st)
            if isinstance(txt,tuple): txt=txt[0]
            en=tio.tell()-1
        except Exception:
            en=st
            while en<len(rsce) and rsce[en]!=0: en+=1
            txt="<?>"
        if en<=st or en>len(rsce):
            en=st
            while en<len(rsce) and rsce[en]!=0: en+=1
        strs.append((st-so,txt))
        q=en+1
    return strs

for SC in SCENES:
    jp,_=get_rsce(src,sp_,SC)
    kr,_=get_rsce(dat,dp,SC)
    if jp is None or kr is None:
        print(f"scene {SC}: 추출실패"); continue
    js=walk(jp,mini_ex); ks=walk(kr,mini_kr)
    jsel=[i for i,(_,t) in enumerate(js) if t=="select"]
    ksel=[i for i,(_,t) in enumerate(ks) if t=="select"]
    jnot=[i for i,(_,t) in enumerate(js) if t=="notice"]
    knot=[i for i,(_,t) in enumerate(ks) if t=="notice"]
    ok = len(js)==len(ks) and jsel==ksel and jnot==knot
    print(f"scene {SC}: strs JP {len(js)} / KR {len(ks)}  select JP {jsel} / KR {ksel}  notice JP {jnot} / KR {knot}  {'OK' if ok else '***MISMATCH***'}")
    if not ok:
        # 앞쪽부터 어긋난 지점 찾기
        for i in range(min(len(js),len(ks))):
            tj=js[i][1]; tk=ks[i][1]
            # select/notice/ascii는 그대로 비교, 그 외엔 개수만
            if (tj in ("select","notice")) != (tk in ("select","notice")) or (tj in ("select","notice") and tj!=tk):
                print(("  first div @ord %d: JP=%r KR=%r" % (i,tj[:30],tk[:30])).encode('unicode_escape').decode('ascii'))
                for d in range(max(0,i-3),min(len(js),i+4)):
                    print(("    JP[%d] %r" % (d,js[d][1][:36])).encode('unicode_escape').decode('ascii'))
                for d in range(max(0,i-3),min(len(ks),i+4)):
                    print(("    KR[%d] %r" % (d,ks[d][1][:36])).encode('unicode_escape').decode('ascii'))
                break
