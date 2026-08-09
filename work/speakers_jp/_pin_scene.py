# -*- coding: utf-8 -*-
# 고정오프셋 참조 씬 전용 재빌드 (orddup + 강제 pin). 사용: py _pin_scene.py 4278 4281
#  - force 범위: 그룹 사본을 원본 오프셋에 정렬 + 범위 내 미참조는 JP 원본 바이트 원위치
#    (미니게임 말풍선/카운트다운 등 고정 스트라이드 블록용)
#  - pin_rels: 개별 문자열만 원본 오프셋에 정렬 (화자명/구역명 고정 슬롯. kr 이 JP 슬롯 초과면
#    kr_override 로 짧은 표기 지정)
#  - unref_hi 미만의 미참조 문자열은 서열 위치에 삽입(서수 보존), unref_skip 은 제외
#  ★씬 4278/4281 은 반드시 이 도구로 재빌드 (_rebuild_scenes 사용 시 pin 소실 = 이름판/말풍선 깨짐)
import os
import sys
import json
import struct

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

CONFIG = {
    4278: dict(force=[(4745, 6036)], unref_hi=6268, unref_skip={1568, 1574, 1630, 1636},
               pin_rels={8: None, 13: None, 28: None, 41: None, 111: "계산원",
                         202: None, 351: None}),
    4281: dict(force=[], unref_hi=0, unref_skip=set(),
               pin_rels={8: None, 13: None, 28: None, 41: "여자", 48: "점원"}),
}

DRY = "--dry" in sys.argv
SCENES = [int(a) for a in sys.argv[1:] if a.isdigit()]

spec = ilu.spec_from_file_location("sp", "work/synopsis_jp/_spaced_inplace.py")
mod = ilu.module_from_spec(spec); spec.loader.exec_module(mod)
INIT = open("work/synopsis_jp/lzss_init.bin", "rb").read()
NM = json.load(open("work/names_npc.json", encoding="utf-8"))
TKR = {k.lower(): v for k, v in json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].items()}
INV = {v: k for k, v in TKR.items()}


def enc_kr(s):
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

for SC in SCENES:
    cfg = CONFIG[SC]
    FORCE = cfg["force"]; UNREF_HI = cfg["unref_hi"]
    UNREF_SKIP = cfg["unref_skip"]; PIN_RELS = cfg["pin_rels"]

    def in_force(o):
        return any(lo <= o < hi for lo, hi in FORCE)

    p0 = sp_[SC]; base = src.rfind(b"SCPK", max(0, p0 - 64), p0 + 8)
    nf = struct.unpack_from("<I", src, base + 8)[0]
    sizes = [struct.unpack_from("<I", src, base + 16 + 4 * k)[0] for k in range(nf)]
    scont = bytes(src[base:base + 16 + 4 * nf + sum(sizes)])
    Path("work/_nb.bin").write_bytes(scont)
    scpk = Scpk.from_path(Path("work/_nb.bin")); orig = scpk.rsce
    so = Theirsce(orig).strings_offset
    mini_ex.id = 1
    Path("work/_nb.xml").write_bytes(mini_ex.get_xml_from_theirsce(Theirsce(orig), "Story"))
    d = json.load(open(f"translation/{SC}.json", encoding="utf-8"))
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
    # XML 미포착 이름 포인터 오퍼랜드 (48 20 04 f8 + u16) — _rebuild_scenes 와 동일 처리
    JPTBL = {k.lower(): v for k, v in json.load(open("tbl_all.json", encoding="utf-8"))["TBL"].items()}
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
                kb = enc_kr(kr) if kr else bytes(orig[st:n])
                groups[v] = [("RAW", kb), [p]]
        q += 1
    starts = []
    q = so
    while q < len(orig):
        if orig[q] == 0:
            q += 1; continue
        starts.append(q - so)
        while q < len(orig) and orig[q] != 0:
            q += 1
    starts.append(len(orig) - so)
    unref = [s for s in starts[:-1]
             if s not in groups and s not in normset
             and (s < UNREF_HI or in_force(s) or s in PIN_RELS) and s not in UNREF_SKIP]
    items = sorted(set(list(groups.keys()) + unref + list(PIN_RELS.keys())))
    out = bytearray(orig[:so + 1]); newoff = {}; problems = []
    for o in items:
        pinned = in_force(o) or o in PIN_RELS
        if o == 0 and o in groups:
            # ptr=0 관용(빈 문자열) = JP 처럼 풀 머리 널을 그대로 가리킴 (추가 방출 없음)
            newoff[0] = 0
            continue
        if o in unref:
            st = so + o; n = st
            while n < len(orig) and orig[n] != 0:
                n += 1
            if pinned:
                cur = len(out) - so
                if cur > o:
                    problems.append(f"rel{o}: unref pin 선행초과 +{cur-o}"); continue
                out += b"\x00" * (o - cur)
                nxt = min(s for s in starts if s > o)
                kb = enc_kr(PIN_RELS[o]) if PIN_RELS.get(o) else orig[st:n]
                if len(kb) > nxt - o - 1:
                    problems.append(f"rel{o}: unref kr 슬롯초과 {len(kb)-(nxt-o-1)}B")
                newoff[o] = len(out) - so
                out += kb + b"\x00"
                continue
            out += orig[st:n] + b"\x00"
            continue
        if o not in groups:
            # pin_rels 로 지정됐지만 그룹에 없음(미참조) -> unref 경로에서 이미 처리됐어야 함
            problems.append(f"rel{o}: 그룹/미참조 어느 쪽도 아님"); continue
        e, _ = groups[o]
        if o in PIN_RELS and PIN_RELS[o] is not None:
            b = enc_kr(PIN_RELS[o])
        elif isinstance(e, tuple) and e[0] == "RAW":
            b = e[1]
        else:
            try:
                b = mini_in.get_node_bytes(e)
            except Exception:
                b = b""
        if pinned:
            cur = len(out) - so
            if cur > o:
                problems.append(f"rel{o}: pin 선행초과 +{cur-o}")
                newoff[o] = len(out) - so
                out += b + b"\x00"
                continue
            out += b"\x00" * (o - cur)
            nxt = min(s for s in starts if s > o)
            avail = nxt - o - 1
            if len(b) > avail:
                problems.append(f"rel{o}: kr {len(b)-avail}B 슬롯초과")
        newoff[o] = len(out) - so
        out += b + b"\x00"
    for o, (e, ptrs) in groups.items():
        for p in ptrs:
            struct.pack_into("<H", out, p, newoff[o])
    new = bytes(out)
    ok_sel = new.count(b"select") == orig.count(b"select")
    print(f"scene {SC}: select {new.count(b'select')}/{orig.count(b'select')} pool {len(new)}B (JP {len(orig)}B)")
    for pr in problems:
        print("  " + pr)
    if DRY:
        continue
    if problems or not ok_sel:
        print(f"[STOP] scene {SC}")
        continue
    for o in items:
        if (in_force(o) or o in PIN_RELS) and o in newoff:
            assert newoff[o] == o, f"pin 불일치 rel{o}->{newoff[o]}"
    blobs = parse_blobs(scont)
    _, off, size, idx = next(bb for bb in blobs if bb[0] == "sce")
    blob = comptolib.compress_data(new, version=scpk._rsce_comp_type); how = "greedy"
    if len(blob) > size:
        body = mod.lzss_encode_optimal(new, INIT)
        blob = struct.pack("<b", 1) + struct.pack("<L", len(body)) + struct.pack("<L", len(new)) + body
        assert comptolib.decompress_data(blob) == new
        how = "optimal"
    if len(blob) > size:
        print(f"  [FAIL] blob over by {len(blob)-size}B ({how})")
        continue
    newc = scont[:off] + blob + b"#" * (size - len(blob)) + scont[off + size:]
    q0 = dp[SC]; b2 = dat.rfind(b"SCPK", max(0, q0 - 64), q0 + 8)
    assert bytes(dat[b2:b2 + 4]) == b"SCPK"
    assert b2 + len(newc) <= dp[SC + 1]
    dat[b2:b2 + len(newc)] = newc
    print(f"  [OK] scene {SC} (blob {len(blob)}/{size}B, {how})")

if not DRY:
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    print("[SAVED]")
