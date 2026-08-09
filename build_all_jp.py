#!/usr/bin/env python3
# ============================================================
#  build_all_jp.py -- JP DAT 기반 전 씬 빌드 (translation/*.json 재사용)
#
#  JP THEIRSCE는 압축(comptolib). pythonlib Scpk 클래스로 해제/재압축.
#  각 씬: SCPK 컨테이너 -> Scpk.rsce(해제 THEIRSCE) -> 번역주입 -> 재압축 -> in-place.
#  크기 불변(재압축이 원본 컨테이너 이내면 널패딩). 넘치면 리포트.
#
#  결과: DAT_jp_full.BIN (JP DAT + 전 씬 한글, 폰트슬롯은 별도 repack)
#  이후: repack_psp_dat.py 로 폰트슬롯(13/14/15) 교체 + EBOOT 포인터 갱신.
#
#  사용: py build_all_jp.py [--scenes 4246,4247] [--limit N]
# ============================================================
import argparse
import json
import struct
import sys
import time
from pathlib import Path

PYTHONLIB = r"D:\PythonLib"
PTR = 0x126F90


def read_ptrs(eb, dat_size):
    ptrs = []
    i = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + i*4)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size*1.05):
            break
        ptrs.append(v)
        i += 1
        if i > 40000:
            break
    return ptrs


def parse_blobs(cont):
    """SCPK 컨테이너 -> 블롭목록 [(kind, off, size, size_idx)]. sce=THEIRSCE."""
    flags = struct.unpack_from("<H", cont, 6)[0]
    n = struct.unpack_from("<I", cont, 8)[0]
    sizes = [struct.unpack_from("<I", cont, 16+4*k)[0] for k in range(n)]
    cur = 16 + 4*n
    blobs = []
    idx = 0
    if flags & 0x1:
        blobs.append(("map", cur, sizes[idx], idx)); cur += sizes[idx]; idx += 1
    if flags & 0x2:
        total = struct.unpack_from("<H", cont, cur)[0]
        blobs.append(("chr_hdr", cur, sizes[idx], idx)); cur += sizes[idx]; idx += 1
        for _ in range(total):
            blobs.append(("chr", cur, sizes[idx], idx)); cur += sizes[idx]; idx += 1
    if flags & 0x4:
        blobs.append(("sce", cur, sizes[idx], idx)); cur += sizes[idx]; idx += 1
    if flags & 0x8:
        blobs.append(("unk", cur, sizes[idx], idx)); cur += sizes[idx]; idx += 1
    return blobs


def swap_theirsce(cont, new_rsce_raw, comp_type, comptolib):
    """THEIRSCE 블롭만 새 재압축 블롭으로 교체 (map/chars/unk 원본 유지)."""
    blobs = parse_blobs(cont)
    _, off, size, idx = next(b for b in blobs if b[0] == "sce")
    nb = comptolib.compress_data(new_rsce_raw, version=comp_type)
    if len(nb) % 4:
        nb = nb + b"#" * (4 - len(nb) % 4)
    out = bytearray(cont)
    struct.pack_into("<I", out, 16 + 4*idx, len(nb))
    return bytes(out[:off]) + nb + bytes(out[off+size:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default="DAT.BIN")
    ap.add_argument("--eboot", default="ULJS00132_EBOOT.BIN")
    ap.add_argument("--tbl-extract", default="tbl_all.json")
    ap.add_argument("--tbl-insert", default="tbl_full_kr.json")
    ap.add_argument("--trans-dir", default="translation")
    ap.add_argument("--out", default="DAT_jp_full.BIN")
    ap.add_argument("--scenes", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="build_jp_report.json")
    args = ap.parse_args()

    sys.path.insert(0, PYTHONLIB)
    sys.path.insert(0, ".")
    from pythonlib.utils import comptolib
    from pythonlib.formats.rebirth.scpk import Scpk
    from pythonlib.formats.rebirth.theirsce import Theirsce
    from story_pipeline_bin import make_mini
    from build_scene import inject_translation
    from lxml import etree
    import re as _re

    # NPC 화자명(Speakers) 한글 사전 (jp 원문 정확일치 -> kr). 파티원 <Tag>/시스템은 미등록 -> 원문유지.
    _NM = {}
    _npc_path = Path("work/names_npc.json")
    if _npc_path.exists():
        _NM = json.load(open(_npc_path, encoding="utf-8"))
    _TAGRE = _re.compile(r"<.*?>")

    def fill_speakers(xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        filled = 0
        for e in root.findall(".//Speakers/Entry"):
            jt = e.find("JapaneseText")
            et = e.find("EnglishText")
            if jt is None or et is None:
                continue
            t = jt.text or ""
            if t in _NM:
                et.text = _NM[t]
                filled += 1
        if filled:
            tree.write(xml_path, encoding="UTF-8", pretty_print=True)
        return filled

    dat = bytearray(Path(args.dat).read_bytes())
    ptrs = read_ptrs(Path(args.eboot).read_bytes(), len(dat))
    print(f"[i] JP DAT {len(dat)}B, 포인터 {len(ptrs)}개")

    mini_ex = make_mini(args.tbl_extract)
    mini_in = make_mini(args.tbl_insert)
    Path("work").mkdir(exist_ok=True)
    tmp = "work/_bjp.bin"

    if args.scenes:
        scenes = [int(s) for s in args.scenes.split(",") if s.strip()]
    else:
        scenes = sorted(int(p.stem) for p in Path(args.trans_dir).glob("*.json")
                        if p.stem.isdigit())
    if args.limit:
        scenes = scenes[:args.limit]
    print(f"[i] 대상 씬 {len(scenes)}개")

    ok, over, err = [], [], []
    t0 = time.time()
    for n, sc in enumerate(scenes, 1):
        try:
            p0, p1 = ptrs[sc], ptrs[sc+1]
            base = dat.rfind(b"SCPK", max(0, p0-64), p0+8)
            if base < 0:
                err.append({"scene": sc, "why": "SCPK 없음"})
                continue
            nf = struct.unpack_from("<I", dat, base+8)[0]
            sizes = [struct.unpack_from("<I", dat, base+16+4*k)[0] for k in range(nf)]
            cont_end = base + 16 + 4*nf + sum(sizes)
            cont = bytes(dat[base:cont_end])
            Path(tmp).write_bytes(cont)

            scpk = Scpk.from_path(Path(tmp))
            if not scpk.rsce or scpk.rsce[:8] != b"THEIRSCE":
                err.append({"scene": sc, "why": "THEIRSCE 없음"})
                continue
            comp_type = scpk._rsce_comp_type

            mini_ex.id = 1
            xml = mini_ex.get_xml_from_theirsce(Theirsce(scpk.rsce), "Story")
            Path(f"work/{sc}_jp.xml").write_bytes(xml)
            data = json.load(open(f"{args.trans_dir}/{sc}.json", encoding="utf-8"))
            inject_translation(f"work/{sc}_jp.xml", f"work/{sc}_jpKR.xml",
                               data.get("lines", []))
            fill_speakers(f"work/{sc}_jpKR.xml")   # NPC 화자명 한글 주입

            mini_in.id = 1
            nt = mini_in.get_new_theirsce(Theirsce(scpk.rsce),
                                          Path(f"work/{sc}_jpKR.xml"))
            nt.seek(0)
            new_rsce = nt.read()
            # THEIRSCE 블롭만 교체 (map/chars/unk 원본 유지 -> 크기변동 최소)
            new_cont = swap_theirsce(cont, new_rsce, comp_type, comptolib)

            # 안전여유 = cont_end 이후 연속 널 (다음 SCPK 머리 전까지)
            null_run = 0
            q = cont_end
            while q < len(dat) and dat[q] == 0 and null_run < 8192:
                null_run += 1
                q += 1
            safe_max = (cont_end - base) + null_run
            if len(new_cont) > safe_max:
                over.append({"scene": sc, "over": len(new_cont)-safe_max})
                continue
            # base~ 새컨테이너 + 널패딩 (원래 컨테이너+널run 범위 안)
            end = base + safe_max
            dat[base:end] = new_cont + b"\x00"*(safe_max-len(new_cont))
            ok.append(sc)
        except Exception as e:
            err.append({"scene": sc, "why": f"{type(e).__name__}: {e}"})

        if n % 50 == 0 or n == len(scenes):
            el = time.time()-t0
            print(f"  [{n}/{len(scenes)}] OK {len(ok)} / 초과 {len(over)} / "
                  f"에러 {len(err)}  ({el:.0f}s)", flush=True)

    Path(args.out).write_bytes(bytes(dat))
    print(f"\n빌드 완료: OK {len(ok)} / 초과 {len(over)} / 에러 {len(err)}")
    print(f"  -> {args.out} ({len(dat)}B, 원본과 크기동일={len(dat)==Path(args.dat).stat().st_size})")
    if over:
        print(f"\n[초과 {len(over)}씬] (번역 줄여야):")
        for o in over[:20]:
            print(f"  씬 {o['scene']}: +{o['over']}B")
    if err:
        print(f"\n[에러 {len(err)}씬]:")
        for e in err[:20]:
            print(f"  씬 {e['scene']}: {e['why']}")
    json.dump({"ok": ok, "over": over, "err": err},
              open(args.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n리포트 -> {args.report}")
    print("다음: py repack_psp_dat.py --eboot ULJS00132_EBOOT.BIN --dat DAT_jp_full.BIN "
          "--replace 13:00013_CN.bin --replace 14:00014_hangul_full.bin "
          "--replace 15:00015_CN.bin --out-dat DAT_jp_final.BIN --out-eboot EBOOT_jp_new.BIN")


if __name__ == "__main__":
    main()
