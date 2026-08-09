#!/usr/bin/env python3
# 모든 스킷 슬롯 열거: 각 슬롯을 미스얼라인 보정 해제 -> PAK2(offsets[0]=0x20)+THEIRSCE 확인.
#  스킷 = DAT 슬롯 1개(압축 PAK2). 결과: 슬롯번호 + 실제시작델타 + 첫 대사(스킷 식별).
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

mext = make_mini("tbl_all.json")
mext.id = 1
PAK2SIG = struct.pack("<I", 0x20)


def try_slot(s):
    lo, hi = ptrs[s], ptrs[s + 1]
    if hi - lo < 20:
        return None
    for delta in range(-64, 9):
        o = lo + delta
        if o < 0 or dat[o] not in (1, 3):
            continue
        try:
            csz = struct.unpack_from("<I", dat, o + 1)[0]
            if not (0 < csz <= hi - o + 64):
                continue
            d = comptolib.decompress_data(dat[o:o + 9 + csz])
        except Exception:
            continue
        if d[:4] != PAK2SIG or b"THEIRSCE" not in d:
            continue
        try:
            rsce = pak2lib.get_theirsce_from_pak2(d)
            if rsce[:8] != b"THEIRSCE":
                continue
            xml = etree.fromstring(mext.get_xml_from_theirsce(Theirsce(rsce), "Story"))
            texts = [e.findtext("JapaneseText") or "" for e in xml.iter("Entry")]
            first = next((t for t in texts if t.strip()), "")
            return {"slot": s, "delta": delta, "dlen": len(d), "rsce_len": len(rsce),
                    "n": len(texts), "first": first[:40]}
        except Exception:
            continue
    return None


def main():
    skits = []
    for s in range(len(ptrs) - 1):
        r = try_slot(s)
        if r:
            skits.append(r)
            print(f"  슬롯 {r['slot']:5d} d{r['delta']:+d} rsce{r['rsce_len']:6d} "
                  f"n{r['n']:3d} | {r['first']!r}", flush=True)
        if s % 2000 == 0:
            print(f"  ...{s}", flush=True)
    print(f"스킷 슬롯 {len(skits)}개")
    json.dump(skits, open("work/skit_jp/_skits.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
