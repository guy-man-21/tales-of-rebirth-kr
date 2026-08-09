# -*- coding: utf-8 -*-
# 전 씬 화자명 한글 주입: 클린 DAT.BIN에서 대사+화자 재빌드 -> DAT_jp_final 제자리 기록.
#  대사 재빌드는 build_all_jp와 동일 경로(재현 검증됨). 화자는 work/names_npc.json 정확일치 채움.
#  제자리(현재 슬롯 컨테이너+널run 범위 안)만 기록 -> 다른 슬롯/EBOOT 불변. 초과 씬은 스킵+리포트.
import os, struct, json, sys, glob, re
os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib"); sys.path.insert(0, ".")
from pathlib import Path
from lxml import etree
from pythonlib.formats.rebirth.scpk import Scpk
from pythonlib.formats.rebirth.theirsce import Theirsce
from story_pipeline_bin import make_mini
from build_scene import inject_translation
from build_all_jp import swap_theirsce
from pythonlib.utils import comptolib

CHECK = "--check" in sys.argv


def rebuild_theirsce(orig, xmlpath, mini_in):
    """★orddup 재빌드 (2026-07-24 실기검증 = 선택지 해법 최종 확정).
    근본원인: 게임은 선택지를 '문자열 서수'(풀에서 널 단위 순번)로 참조(슬롯2 STRICT존과 동일 패턴).
    get_new_theirsce 는 중복 제거+문서순 재배열로 서열을 바꿔 일부 선택지가 깨짐.
    해법: 모든 포인터를 '자기 원본 오프셋' 그룹으로 -> **사본 전부 보존**(중복 제거 금지),
    **원본 오프셋 오름차순 기록**(=원본 서열 재현). 포인터는 각자 자기 사본으로. 축약 불필요.
    씬4232 실기: 선택지 정상+대사 온전+크래시 없음. (v2/v3 등 서열 깨는 방식은 전부 실패.)"""
    so = Theirsce(orig).strings_offset
    root = etree.parse(xmlpath).getroot()
    ents = [e for e in root.iter("Entry")
            if e.find("Id") is not None and e.find("Id").text != "-1"
            and e.find("PointerOffset") is not None
            and e.find("PointerOffset").text not in (None, "-1")]
    groups = {}   # 원본 rel -> (엔트리, [포인터위치들])  = 사본 단위
    for e in ents:
        for x in e.find("PointerOffset").text.split(","):
            p = int(x)
            o = struct.unpack_from("<H", orig, p)[0]
            groups.setdefault(o, [e, []])[1].append(p)
    out = bytearray(orig[:so + 1])
    newoff = {}
    for o in sorted(groups):
        e, _ = groups[o]
        newoff[o] = len(out) - so
        try:
            b = mini_in.get_node_bytes(e)
        except Exception:
            b = b""
        out += b + b"\x00"
    for o, (e, ptrs) in groups.items():
        for p in ptrs:
            struct.pack_into("<H", out, p, newoff[o])
    return bytes(out)


_OPT = None   # 최적파스 인코더 lazy 로드


def compress_best(scont, new_rsce, comp_type, limit):
    """greedy(DLL) 먼저, 초과 시 최적파스(type1) 재시도. (블롭교체 컨테이너, 성공여부) 반환."""
    global _OPT
    newc = swap_theirsce(scont, new_rsce, comp_type, comptolib)
    if len(newc) <= limit:
        return newc, "greedy"
    # 최적파스 (type1)
    if _OPT is None:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("sp_inp", "work/synopsis_jp/_spaced_inplace.py")
        m = ilu.module_from_spec(spec)
        spec.loader.exec_module(m)
        _OPT = (m.lzss_encode_optimal, open("work/synopsis_jp/lzss_init.bin", "rb").read())
    enc, init = _OPT
    body = enc(new_rsce, init)
    blob = struct.pack("<b", 1) + struct.pack("<L", len(body)) + struct.pack("<L", len(new_rsce)) + body
    if comptolib.decompress_data(blob) != new_rsce:      # DLL 라운드트립 검증(게임 호환)
        return newc, "rt-fail"
    from build_all_jp import parse_blobs
    blobs = parse_blobs(scont)
    _, off, size, idx = next(b for b in blobs if b[0] == "sce")
    nb = blob
    if len(nb) % 4:
        nb = nb + b"#" * (4 - len(nb) % 4)
    outc = bytearray(scont)
    struct.pack_into("<I", outc, 16 + 4 * idx, len(nb))
    newc2 = bytes(outc[:off]) + nb + bytes(outc[off + size:])
    if len(newc2) <= limit:
        return newc2, "optimal"
    return (newc if len(newc) < len(newc2) else newc2), "over"
NM = json.load(open("work/names_npc.json", encoding="utf-8"))
PTR = 0x126F90
def rp(buf, dsize):
    p=[];k=0
    while True:
        v=struct.unpack_from("<I",buf,PTR+k*4)[0]
        if k>0 and (v<p[-1] or v>dsize*1.05):break
        p.append(v);k+=1
        if k>40000:break
    return p

mini_ex=make_mini("tbl_all.json"); mini_in=make_mini("tbl_full_kr.json")
src=open("DAT.BIN","rb").read(); sp=rp(open("ULJS00132_EBOOT.BIN","rb").read(),len(src))
dat=bytearray(open("DAT_jp_final.BIN","rb").read()); fp=rp(open("EBOOT_jp_new.BIN","rb").read(),len(dat))

scenes=sorted(int(os.path.basename(f)[:-5]) for f in glob.glob("translation/*.json"))
def slot(buf,ptrs,sc):
    p0=ptrs[sc]
    base=buf.rfind(b"SCPK",max(0,p0-64),p0+8)
    if base<0: return None
    nf=struct.unpack_from("<I",buf,base+8)[0]
    sizes=[struct.unpack_from("<I",buf,base+16+4*k)[0] for k in range(nf)]
    ce=base+16+4*nf+sum(sizes)
    return base,ce

ok=names_tot=skip=over=noscene=0; overs=[]; miss=set(); opt_used=[]
for n,sc in enumerate(scenes,1):
    s=slot(bytes(src),sp,sc)
    if s is None: noscene+=1; continue
    sbase,sce=s
    scont=bytes(src[sbase:sce])
    Path("work/_pa.bin").write_bytes(scont)
    try:
        scpk=Scpk.from_path(Path("work/_pa.bin"))
        if not scpk.rsce or scpk.rsce[:8]!=b"THEIRSCE": skip+=1; continue
    except Exception:
        skip+=1; continue
    ct=scpk._rsce_comp_type
    mini_ex.id=1
    xml=mini_ex.get_xml_from_theirsce(Theirsce(scpk.rsce),"Story"); Path(f"work/_pa.xml").write_bytes(xml)
    data=json.load(open(f"translation/{sc}.json",encoding="utf-8"))
    inject_translation("work/_pa.xml","work/_pak.xml",data.get("lines",[]))
    # 화자 주입
    tree=etree.parse("work/_pak.xml"); root=tree.getroot(); nf_names=0
    for e in root.findall(".//Speakers/Entry"):
        jt=e.find("JapaneseText"); et=e.find("EnglishText")
        if jt is None or et is None: continue
        t=jt.text or ""
        if t in NM: et.text=NM[t]; nf_names+=1
    if nf_names: tree.write("work/_pak.xml",encoding="UTF-8",pretty_print=True)
    mini_in.id=1
    # ★orddup 경로(서열 보존) + greedy/최적파스 압축 캐스케이드
    new_rsce=rebuild_theirsce(scpk.rsce,"work/_pak.xml",mini_in)
    # 현재 DAT_jp_final 슬롯
    f=slot(bytes(dat),fp,sc)
    if f is None: noscene+=1; continue
    fbase,fce=f
    nr=0;q=fce
    while q<len(dat) and dat[q]==0 and nr<8192: nr+=1;q+=1
    safe=(fce-fbase)+nr
    newc,how=compress_best(scont,new_rsce,ct,safe)
    if len(newc)>safe:
        over+=1; overs.append((sc,len(newc)-safe)); continue
    if not CHECK:
        dat[fbase:fbase+safe]=newc+b"\x00"*(safe-len(newc))
    ok+=1; names_tot+=nf_names
    if how=="optimal": opt_used.append(sc)
    if n%100==0: print(f"  [{n}/{len(scenes)}] OK {ok} (최적압축 {len(opt_used)}) 이름{names_tot} 초과{over} 스킵{skip}",flush=True)

print(f"\n완료: OK {ok} / 이름주입 {names_tot} / 초과 {over} / 비THEIRSCE {skip} / 비씬 {noscene}")
if overs:
    print("초과 씬:", overs[:30])
if not CHECK and ok:
    open("DAT_jp_final.BIN","wb").write(bytes(dat))
    print("[OK] DAT_jp_final 화자명 전 씬 주입 (제자리, 크기불변)")
