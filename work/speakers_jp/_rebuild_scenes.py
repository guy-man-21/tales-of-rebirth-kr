# -*- coding: utf-8 -*-
# 지정 씬 재빌드 (orddup+pin, 클린 템플릿 제자리 블롭 교체). 사용: py rebuild_scenes.py 4237 4280 ...
import os, sys, json, struct
os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib"); sys.path.insert(0, ".")
from pathlib import Path
from lxml import etree
from pythonlib.formats.rebirth.scpk import Scpk
from pythonlib.formats.rebirth.theirsce import Theirsce
from pythonlib.utils import comptolib
from story_pipeline_bin import make_mini
from build_scene import inject_translation
from build_all_jp import parse_blobs
import importlib.util as ilu

spec = ilu.spec_from_file_location("sp", "work/synopsis_jp/_spaced_inplace.py")
mod = ilu.module_from_spec(spec); spec.loader.exec_module(mod)
INIT = open("work/synopsis_jp/lzss_init.bin", "rb").read()
TKR = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
INV = {v: k for k, v in TKR.items()}
JPTBL = {k.lower(): v for k, v in json.load(open("tbl_all.json", encoding="utf-8"))["TBL"].items()}
NM = json.load(open("work/names_npc.json", encoding="utf-8"))
PINS = {}
if os.path.exists("work/edit/pins.json"):
    PINS = {int(k): {int(r): v for r, v in vv.items()}
            for k, vv in json.load(open("work/edit/pins.json", encoding="utf-8")).items()}


def enc(s):
    o = bytearray()
    for c in s:
        o.append(0x20) if c == " " else o.extend(bytes.fromhex(INV[c]))
    return bytes(o)


def rp(buf, ds):
    p = []; k = 0
    while True:
        v = struct.unpack_from("<I", buf, 0x126F90 + k * 4)[0]
        if k > 0 and (v < p[-1] or v > ds * 1.05):
            break
        p.append(v); k += 1
        if k > 40000:
            break
    return p


src = open("DAT.BIN", "rb").read()
sp_ = rp(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
dp = rp(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
mini_ex = make_mini("tbl_all.json")
mini_in = make_mini("tbl_full_kr.json")

for sc in [int(x) for x in sys.argv[1:]]:
    p0 = sp_[sc]; base = src.rfind(b"SCPK", max(0, p0 - 64), p0 + 8)
    nf = struct.unpack_from("<I", src, base + 8)[0]
    sizes = [struct.unpack_from("<I", src, base + 16 + 4 * k)[0] for k in range(nf)]
    scont = bytes(src[base:base + 16 + 4 * nf + sum(sizes)])
    Path("work/_nb.bin").write_bytes(scont)
    scpk = Scpk.from_path(Path("work/_nb.bin")); orig = scpk.rsce
    so = Theirsce(orig).strings_offset
    mini_ex.id = 1
    Path("work/_nb.xml").write_bytes(mini_ex.get_xml_from_theirsce(Theirsce(orig), "Story"))
    d = json.load(open(f"translation/{sc}.json", encoding="utf-8"))
    inject_translation("work/_nb.xml", "work/_nbk.xml", d.get("lines", []))
    tree = etree.parse("work/_nbk.xml"); root = tree.getroot()
    for e in root.findall(".//Speakers/Entry"):
        jt = e.find("JapaneseText"); et = e.find("EnglishText")
        if jt is not None and et is not None and (jt.text or "") in NM:
            et.text = NM[jt.text]
    mini_in.id = 1
    ents = [e for e in root.iter("Entry")
            if e.find("Id") is not None and e.find("Id").text != "-1"
            and e.find("PointerOffset") is not None
            and e.find("PointerOffset").text not in (None, "-1")]
    ex = PINS.get(sc, {})
    groups = {}; normset = set()
    for e in ents:
        for x in e.find("PointerOffset").text.split(","):
            p = int(x)
            o = struct.unpack_from("<H", orig, p)[0]
            groups.setdefault(o, [e, []])[1].append(p)
            o2 = o
            while so + o2 < len(orig) and orig[so + o2] == 0:
                o2 += 1
            normset.add(o2)
    # ★XML 미포착 이름 포인터 오퍼랜드 (`48 20 04 f8` + u16 풀오프셋, 2026-07-30):
    #  이름판 등 화자 지정 없는 창의 이름 참조. 미포착분은 여기서 일반 포인터처럼 갱신.
    #  타깃이 미참조 문자열이면 names_npc 번역(없으면 JP 원바이트)으로 삽입.
    known = {p for _, (e_, ptrs_) in groups.items() for p in ptrs_}
    q = 0
    while True:
        q = orig.find(b"\x48\x20\x04\xf8", q, so - 6)
        if q < 0:
            break
        p = q + 4
        v = struct.unpack_from("<H", orig, p)[0]
        tgt_ok = so + v < len(orig) and orig[so + v] != 0 and (v == 0 or orig[so + v - 1] == 0)
        if p not in known and tgt_ok:
            if v in groups:
                groups[v][1].append(p)
            else:
                st = so + v; n = st
                while n < len(orig) and orig[n] != 0:
                    n += 1
                jpname = ""
                i2 = st
                while i2 < n:
                    if orig[i2] < 0x80:
                        jpname += chr(orig[i2]); i2 += 1
                        continue
                    ch = JPTBL.get(orig[i2:i2 + 2].hex().lower())
                    if ch is None:
                        jpname = None; break
                    jpname += ch; i2 += 2
                kr = NM.get(jpname or "")
                kb = enc(kr) if kr else bytes(orig[st:n])
                groups[v] = [("RAW", kb), [p]]
        q += 1
    allstarts = []
    q = so
    while q < len(orig):
        if orig[q] == 0:
            q += 1; continue
        allstarts.append(q - so)
        while q < len(orig) and orig[q] != 0:
            q += 1
    unref = [o for o in allstarts if o not in groups and o not in normset and o in ex]
    items = sorted(set(list(groups.keys()) + unref))
    out = bytearray(orig[:so + 1]); newoff = {}; overshoot = 0
    for o in items:
        if o in groups:
            e, _ = groups[o]
            if isinstance(e, tuple) and e[0] == "RAW":
                b = e[1]
            else:
                try:
                    b = mini_in.get_node_bytes(e)
                except Exception:
                    b = b""
            newoff[o] = len(out) - so
            out += b + b"\x00"
        else:
            cur = len(out) - so
            if cur > o:
                overshoot += 1
            else:
                out += b"\x00" * (o - cur)
            st = so + o; n = st
            while n < len(orig) and orig[n] != 0:
                n += 1
            kb = enc(ex[o])
            assert len(kb) <= n - st
            newoff[o] = len(out) - so
            out += kb + b"\x00"
    for o, (e, ptrs) in groups.items():
        for p in ptrs:
            struct.pack_into("<H", out, p, newoff[o])
    new = bytes(out)
    assert new.count(b"select") == orig.count(b"select") and not overshoot
    blobs = parse_blobs(scont)
    _, off, size, idx = next(bb for bb in blobs if bb[0] == "sce")
    blob = comptolib.compress_data(new, version=scpk._rsce_comp_type); how = "greedy"
    if len(blob) > size:
        body = mod.lzss_encode_optimal(new, INIT)
        blob = struct.pack("<b", 1) + struct.pack("<L", len(body)) + struct.pack("<L", len(new)) + body
        assert comptolib.decompress_data(blob) == new
        how = "optimal"
    if len(blob) > size:
        print(f"[FAIL] scene {sc}: over by {len(blob)-size}B ({how})")
        continue
    newc = scont[:off] + blob + b"#" * (size - len(blob)) + scont[off + size:]
    q0 = dp[sc]; b2 = dat.rfind(b"SCPK", max(0, q0 - 64), q0 + 8)
    assert bytes(dat[b2:b2 + 4]) == b"SCPK"
    assert b2 + len(newc) <= dp[sc + 1], f"scene {sc}: next-file overrun"
    dat[b2:b2 + len(newc)] = newc
    print(f"[OK] scene {sc} (blob {len(blob)}/{size}B, {how})")

open("DAT_jp_final.BIN", "wb").write(bytes(dat))
print("[SAVED]")
