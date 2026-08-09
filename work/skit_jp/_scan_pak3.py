#!/usr/bin/env python3
# DAT 전 슬롯을 PAK(0/1/3)로 풀어 서브파일에서 스킷 THEIRSCE 를 찾는다.
#  슬롯(필요시 해제) -> PAK 판별 -> 서브파일 각각 해제 -> THEIRSCE 매직 + 스킷키워드 검색.
import json
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

Tall = json.load(open("tbl_all.json", encoding="utf-8"))
Tall = Tall.get("TBL", Tall)
inv = {}
for k, v in Tall.items():
    inv.setdefault(v, k)


def enc(s):
    o = b""
    for c in s:
        if c in inv:
            o += bytes.fromhex(inv[c])
        elif ord(c) < 0x80:
            o += bytes([ord(c)])
        else:
            return None
    return o


# 스킷 제목 고유어 (EBOOT 스킷 접미에서 확인된 것들)
KW = [enc(x) for x in ("コワイお話", "みだしなみ", "バトルブック", "占い指南", "自己紹介")]
KW = [k for k in KW if k]

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


def parse_pak_subfiles(buf):
    """PAK0/1/3 서브파일 blob 목록 반환. 실패 시 []."""
    if len(buf) < 8:
        return []
    n = struct.unpack_from("<I", buf, 0)[0]
    if not (0 < n < 4096) or (n + 1) * 4 > len(buf):
        return []
    try:
        offs = list(struct.unpack_from("<%dI" % n, buf, 4))
    except Exception:
        return []
    # PAK3: 오프셋 오름차순, 첫 오프셋 >= 헤더크기
    hdr = 4 + n * 4
    if not all(offs[k] < offs[k + 1] for k in range(n - 1)):
        return []
    if offs[0] < hdr or offs[-1] > len(buf):
        return []
    offs2 = offs + [len(buf)]
    subs = []
    for a, b in zip(offs2[:-1], offs2[1:]):
        if 0 <= a < b <= len(buf):
            subs.append(buf[a:b])
    return subs


hits = []
for s in range(len(ptrs) - 1):
    lo, hi = ptrs[s], ptrs[s + 1]
    if hi - lo < 12:
        continue
    blob = dat[lo:hi]
    cands = [blob]
    if comptolib.is_compressed(blob):
        try:
            cands.append(comptolib.decompress_data(blob))
        except Exception:
            pass
    for cand in cands:
        subs = parse_pak_subfiles(cand)
        if not subs:
            continue
        for si, sub in enumerate(subs):
            d = sub
            if comptolib.is_compressed(sub):
                try:
                    d = comptolib.decompress_data(sub)
                except Exception:
                    d = sub
            if b"THEIRSCE" in d:
                kw = any(k in d for k in KW)
                hits.append({"slot": s, "off": lo, "sub": si, "nsub": len(subs),
                             "sublen": len(d), "kw": kw})
                tp = "SKIT-KW" if kw else "theirsce"
                print(f"  [{tp}] 슬롯 {s} @0x{lo:X} sub {si}/{len(subs)} len {len(d)}", flush=True)
    if s % 2000 == 0:
        print(f"  ...{s}/{len(ptrs)-1} (hits {len(hits)})", flush=True)

print(f"완료. 스킷 서브파일 {len(hits)}개")
json.dump(hits, open("work/skit_jp/_skit_pak3.json", "w"), ensure_ascii=False, indent=1)
