#!/usr/bin/env python3
# ============================================================
#  build_dat_jp.py -- 초과 씬만 확장 재조립 (품질 유지, 축약 X)
#
#  build_all_jp 는 697씬을 크기불변 in-place 로 DAT_jp_full 에 넣고, 초과 35씬은
#  스킵(원문 일본어)한다. 이 스크립트는 그 초과 씬만 확장된 컨테이너로 교체하고,
#  그 씬 뒤쪽 데이터를 밀며 뒤쪽 EBOOT 포인터만 갱신한다.
#
#  - 입력 DAT = DAT_jp_full.BIN (697씬 한글 완료). 앞쪽 697은 손대지 않음.
#  - 초과 씬만: THEIRSCE 블롭만 재압축 교체(무손실). 널여유 제한 없이 확장 허용.
#  - 컨테이너 단위 재조립: 확장분을 뒤로 누적, 포인터 p 새 위치 = p + (p 앞 확장 누적).
#    SCPK 가 슬롯경계 넘어도(크로스) 바이트 시퀀스라 무관.
#
#  사용: py build_dat_jp.py   (build_jp_report.json 의 over 씬을 확장)
# ============================================================
import argparse
import bisect
import json
import struct
import sys
import time
from pathlib import Path

PYTHONLIB = r"D:\PythonLib"
PTR = 0x126F90


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default="DAT_jp_full.BIN")   # 697씬 한글 완료본
    ap.add_argument("--src-dat", default="DAT.BIN")       # 원본(초과씬 원문 추출용)
    ap.add_argument("--eboot", default="ULJS00132_EBOOT.BIN")
    ap.add_argument("--tbl-extract", default="tbl_all.json")
    ap.add_argument("--tbl-insert", default="tbl_full_kr.json")
    ap.add_argument("--trans-dir", default="translation")
    ap.add_argument("--report", default="build_jp_report.json")
    ap.add_argument("--out-dat", default="DAT_jp_full.BIN")
    ap.add_argument("--out-eboot", default="EBOOT_jp_full.BIN")
    args = ap.parse_args()

    sys.path.insert(0, PYTHONLIB)
    sys.path.insert(0, ".")
    from pythonlib.utils import comptolib
    from pythonlib.formats.rebirth.scpk import Scpk
    from pythonlib.formats.rebirth.theirsce import Theirsce
    from story_pipeline_bin import make_mini
    from build_scene import inject_translation
    from build_all_jp import swap_theirsce

    dat = Path(args.dat).read_bytes()          # 697 한글 완료본
    src = Path(args.src_dat).read_bytes()       # 원본 (초과씬 원문)
    eboot = bytearray(Path(args.eboot).read_bytes())
    ptrs = []
    i = 0
    while True:
        v = struct.unpack_from("<I", eboot, PTR + i*4)[0]
        if i > 0 and (v < ptrs[-1] or v > len(dat)*1.05):
            break
        ptrs.append(v); i += 1
        if i > 40000:
            break

    over = [o["scene"] for o in json.load(open(args.report, encoding="utf-8"))["over"]]
    print(f"[i] 확장 대상 초과 씬 {len(over)}개")

    mini_ex = make_mini(args.tbl_extract)
    mini_in = make_mini(args.tbl_insert)
    Path("work").mkdir(exist_ok=True)
    tmp = "work/_bddjp.bin"

    # 초과 씬 확장 컨테이너 생성. edits[base] = (cont_end, new_cont). base 는 dat 기준.
    edits = {}
    ok = err = 0
    errs = []
    t0 = time.time()
    for sc in over:
        try:
            p0, p1 = ptrs[sc], ptrs[sc+1]
            # 초과씬은 dat(=DAT_jp_full)에서 원문 일본어 상태. 원본 src 에서 컨테이너 추출.
            base = src.rfind(b"SCPK", max(0, p0-64), p0+8)
            if base < 0:
                err += 1; errs.append((sc, "SCPK 없음")); continue
            nf = struct.unpack_from("<I", src, base+8)[0]
            sizes = [struct.unpack_from("<I", src, base+16+4*k)[0] for k in range(nf)]
            cont_end = base + 16 + 4*nf + sum(sizes)
            cont = src[base:cont_end]
            Path(tmp).write_bytes(cont)
            scpk = Scpk.from_path(Path(tmp))
            if not scpk.rsce or scpk.rsce[:8] != b"THEIRSCE":
                err += 1; errs.append((sc, "THEIRSCE 없음")); continue
            comp_type = scpk._rsce_comp_type
            mini_ex.id = 1
            xml = mini_ex.get_xml_from_theirsce(Theirsce(scpk.rsce), "Story")
            Path(f"work/{sc}_jp.xml").write_bytes(xml)
            data = json.load(open(f"{args.trans_dir}/{sc}.json", encoding="utf-8"))
            inject_translation(f"work/{sc}_jp.xml", f"work/{sc}_jpKR.xml",
                               data.get("lines", []))
            mini_in.id = 1
            nt = mini_in.get_new_theirsce(Theirsce(scpk.rsce),
                                          Path(f"work/{sc}_jpKR.xml"))
            nt.seek(0)
            new_cont = swap_theirsce(cont, nt.read(), comp_type, comptolib)
            # 확장 delta 를 2048(섹터) 배수로 패딩 — EBOOT 2차 테이블 등 섹터정렬 참조 보호
            delta = len(new_cont) - (cont_end - base)
            pad = (-delta) % 2048
            new_cont = new_cont + b"\x00" * pad
            # base 는 src 기준. dat(697반영)에서 이 씬은 원문이라 동일 위치.
            edits[base] = (cont_end, new_cont)
            ok += 1
        except Exception as e:
            err += 1; errs.append((sc, f"{type(e).__name__}: {e}"))
    print(f"[i] 확장 컨테이너 생성 OK {ok} / 에러 {err} ({time.time()-t0:.0f}s)")

    # 재조립: dat 를 순회하며 초과씬 컨테이너만 교체, 확장분 누적
    out = bytearray()
    cursor = 0
    shifts = []   # (cont_end_orig, 누적shift)
    cum = 0
    for base in sorted(edits):
        cont_end, new_cont = edits[base]
        out += dat[cursor:base]
        out += new_cont
        cum += len(new_cont) - (cont_end - base)
        shifts.append((cont_end, cum))
        cursor = cont_end
    out += dat[cursor:]
    print(f"[i] 재조립: {len(dat)}B -> {len(out)}B ({len(out)-len(dat):+d})")

    # 포인터: p 이하인 마지막 shift 이전 누적 적용
    sp = [s[0] for s in shifts]
    sc_ = [s[1] for s in shifts]
    for k, p in enumerate(ptrs):
        j = bisect.bisect_right(sp, p) - 1
        struct.pack_into("<I", eboot, PTR + k*4, p + (sc_[j] if j >= 0 else 0))

    Path(args.out_dat).write_bytes(bytes(out))
    Path(args.out_eboot).write_bytes(bytes(eboot))
    print(f"\n완료: 확장 {ok}씬 / 에러 {err}")
    print(f"  -> {args.out_dat} ({len(out)}B), {args.out_eboot}")
    for sc, why in errs[:10]:
        print(f"  씬 {sc}: {why}")
    print("\n다음: repack_psp_dat.py 로 폰트슬롯 교체 (EBOOT_jp_full 입력)")


if __name__ == "__main__":
    main()
