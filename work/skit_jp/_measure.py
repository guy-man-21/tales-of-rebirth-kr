#!/usr/bin/env python3
# 슬롯별 재압축 fit 측정 (축약 작업용). skits/{slot}.json 의 현재 kr 로 측정.
#  orig_len 은 클린 백업(DAT_jp_final_preskit.BIN)에서 읽음(재빌드 함정 회피).
#  출력: 슬롯별 "comp>orig (+delta)" 또는 "OK (-여유)". delta<=0 이면 적합.
#  사용: py work\skit_jp\_measure.py 344,356,364   (쉼표구분 슬롯)
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pythonlib.utils import comptolib
from pythonlib.formats.rebirth import pak2 as pak2lib
from pythonlib.formats.rebirth.theirsce import Theirsce
from story_pipeline_bin import make_mini
from build_scene import inject_translation
from pathlib import Path

PTR = 0x126F90


def read_ptrs(eb, ds):
    p = []; j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > ds * 1.05):
            break
        p.append(v); j += 1
        if j > 40000:
            break
    return p


def find_pak(buf, lo):
    for dl in range(-64, 9):
        o = lo + dl
        if o < 0 or o + 9 > len(buf) or buf[o] not in (1, 3):
            continue
        try:
            csz = struct.unpack_from("<I", buf, o + 1)[0]
            d = comptolib.decompress_data(bytes(buf[o:o + 9 + csz]))
            if d[:4] == struct.pack("<I", 0x20) and b"THEIRSCE" in d:
                return o, 9 + csz, d, buf[o]
        except Exception:
            continue
    return None


src = open("DAT.BIN", "rb").read()
sp = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
dat = open("DAT_jp_final_preskit.BIN", "rb").read()
dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
mex = make_mini("tbl_all.json"); mn = make_mini("tbl_full_kr.json")


def measure(slot, lines):
    rs = find_pak(src, sp[slot]); rd = find_pak(dat, dp[slot])
    if rs is None or rd is None:
        return None, None
    _, _, pak, ct = rs; _, ol, _, _ = rd
    data = pak2lib.get_data(pak); rsce = data.chunks.theirsce
    mex.id = 1
    Path("work/skit_jp/_m.xml").write_bytes(mex.get_xml_from_theirsce(Theirsce(rsce), "Story"))
    inject_translation("work/skit_jp/_m.xml", "work/skit_jp/_mk.xml", lines, field="EnglishText")
    mn.id = 1
    nt = mn.get_new_theirsce(Theirsce(rsce), Path("work/skit_jp/_mk.xml")); nt.seek(0)
    data.chunks.theirsce = nt.read()
    comp = comptolib.compress_data(pak2lib.create_pak2(data), version=ct)
    return len(comp), ol


slots = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else []
n_over = 0
for slot in slots:
    js = json.load(open(f"work/skit_jp/skits/{slot}.json", encoding="utf-8"))
    lines = [l for l in js["lines"] if (l.get("kr") or "").strip()]
    cl, ol = measure(slot, lines)
    if cl is None:
        print(f"slot {slot}: PAK 못찾음")
        continue
    d = cl - ol
    if d > 0:
        n_over += 1
        print(f"slot {slot}: OVER {cl}>{ol} (+{d})  <- {d}B 이상 축약 필요")
    else:
        print(f"slot {slot}: OK  {cl}<={ol} (여유 {-d})")
print(f"--- 초과 {n_over}/{len(slots)} ---")
