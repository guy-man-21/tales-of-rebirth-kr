#!/usr/bin/env python3
# 전 스킷 슬롯(_skits.json)에서 THEIRSCE 대사 추출 -> 슬롯별 번역 코퍼스.
#  출력: work/skit_jp/skits/{slot}.json  ({slot,delta,lines:[{id,jp,kr}]})
#  기존 kr 은 보존(재추출 시).
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
from lxml import etree

dat = open("DAT.BIN", "rb").read()
eb = open("ULJS00132_EBOOT.BIN", "rb").read()
PTR = 0x126F90
ptrs = []
i = 0
while True:
    v = struct.unpack_from("<I", eb, PTR + i * 4)[0]
    if i > 0 and (v < ptrs[-1] or v > len(dat) * 1.05):
        break
    ptrs.append(v)
    i += 1
    if i > 40000:
        break

mex = make_mini("tbl_all.json")
mex.id = 1
skits = json.load(open("work/skit_jp/_skits.json", encoding="utf-8"))
outdir = "work/skit_jp/skits"
os.makedirs(outdir, exist_ok=True)

total_lines = 0
nonempty = 0
for sk in skits:
    slot = sk["slot"]
    start = ptrs[slot] + sk["delta"]
    csz = struct.unpack_from("<I", dat, start + 1)[0]
    pak = comptolib.decompress_data(dat[start:start + 9 + csz])
    rsce = pak2lib.get_theirsce_from_pak2(pak)
    mex.id = 1  # 스킷별 Id 1..N (씬 빌드와 동일)
    xml = etree.fromstring(mex.get_xml_from_theirsce(Theirsce(rsce), "Story"))
    lines = []
    for e in xml.iter("Entry"):
        ide = e.findtext("Id")
        jp = e.findtext("JapaneseText") or ""
        if ide is None or ide.strip() == "-1":
            continue
        if not jp.strip() or jp.strip() == "[VARIABLE]":
            continue
        lines.append({"id": ide.strip(), "jp": jp, "kr": ""})
    outp = f"{outdir}/{slot}.json"
    if os.path.exists(outp):
        old = {l["id"]: l["kr"] for l in json.load(open(outp, encoding="utf-8")).get("lines", [])}
        for l in lines:
            if old.get(l["id"]):
                l["kr"] = old[l["id"]]
    json.dump({"slot": slot, "delta": sk["delta"], "lines": lines},
              open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total_lines += len(lines)
    if lines:
        nonempty += 1

print(f"스킷 {len(skits)}개 중 대사있는 {nonempty}개, 총 {total_lines}줄 -> {outdir}/")
