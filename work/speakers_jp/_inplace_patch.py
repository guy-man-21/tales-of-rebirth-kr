# -*- coding: utf-8 -*-
# 씬 텍스트 '제자리 교체' 정식판 (2026-07-24) - 선택지(select) 깨짐 근본 해결.
#  ★배경: get_new_theirsce 로 문자열 풀을 재작성하면 원본 레이아웃이 바뀌어 선택지가 깨짐.
#    CN 패치판 = 원본 레이아웃 그대로 두고 텍스트만 제자리 교체(그래서 선택지 정상).
#    씬4232 순수 제자리 실기 검증 통과 = 이 방식이 답임 확정.
#  방식: 원본 THEIRSCE 복사 -> 각 문자열을 '원본 슬롯'(다음 참조문자열 시작까지) 안에서 한글로 덮어씀.
#    - 슬롯에 들어가면: kr + 남는자리 널채움(압축 유리).
#    - 초과하면: kr 을 슬롯에 맞게 '뒤에서 축약'(공백/문장부호 우선 제거, 없으면 절단) -> 대사 최대한 살림.
#    ★select/notice 등 인접성 문자열은 원본 그대로(포인터 오프셋 무변경)라 자동 보존됨.
#  컨테이너 초과 씬은 스킵(현행 유지). 코드/포인터/오프셋 일절 무변경.
#  사용: py work\speakers_jp\_inplace_patch.py [--check]
import argparse
import bisect
import glob
import json
import os
import re
import struct
import sys

os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pathlib import Path
from lxml import etree
from pythonlib.formats.rebirth.scpk import Scpk
from pythonlib.formats.rebirth.theirsce import Theirsce
from pythonlib.utils import comptolib
from story_pipeline_bin import make_mini
from build_scene import inject_translation
from build_all_jp import swap_theirsce

PTR = 0x126F90
NM = json.load(open("work/names_npc.json", encoding="utf-8"))
TAGRE = re.compile(rb"<[0-9A-Fa-f]{2}>")   # (미사용, 참고)


def read_ptrs(buf, dsize):
    p = []
    k = 0
    while True:
        v = struct.unpack_from("<I", buf, PTR + k * 4)[0]
        if k > 0 and (v < p[-1] or v > dsize * 1.05):
            break
        p.append(v)
        k += 1
        if k > 40000:
            break
    return p


def slot_of(buf, ptrs, sc):
    p0 = ptrs[sc]
    base = buf.rfind(b"SCPK", max(0, p0 - 64), p0 + 8)
    if base < 0:
        return None
    nf = struct.unpack_from("<I", buf, base + 8)[0]
    sizes = [struct.unpack_from("<I", buf, base + 16 + 4 * k)[0] for k in range(nf)]
    return base, base + 16 + 4 * nf + sum(sizes)


def shrink(b, limit):
    """인코딩된 바이트열 b 를 limit 이내로. 2바이트 문자 경계 보존, 뒤에서 절단."""
    if len(b) <= limit:
        return b
    b = b[:limit]
    # 2바이트(>=0x81) 문자가 반쪽 잘리면 한 바이트 더 제거
    # 앞에서부터 파싱해 경계 확인
    i = 0
    while i < len(b):
        step = 2 if b[i] >= 0x81 else 1
        if i + step > len(b):
            b = b[:i]
            break
        i += step
    return b


def build_inplace(orig, xmlpath, mini_in):
    """제자리 교체. 반환: (bytes, 적합수, 축약수)"""
    so = Theirsce(orig).strings_offset
    root = etree.parse(xmlpath).getroot()
    ents = [e for e in root.iter("Entry")
            if e.find("Id") is not None and e.find("Id").text != "-1"
            and e.find("PointerOffset") is not None
            and e.find("PointerOffset").text not in (None, "-1")]
    alloff = sorted({so + struct.unpack_from("<H", orig, int(x))[0]
                     for e in ents for x in e.find("PointerOffset").text.split(",")})
    out = bytearray(orig)
    fit = cut = 0
    for e in ents:
        st = so + struct.unpack_from("<H", orig, int(e.find("PointerOffset").text.split(",")[0]))[0]
        k = bisect.bisect_right(alloff, st)
        nxt = alloff[k] if k < len(alloff) else len(orig)
        slot = nxt - st - 1                      # 널 1개 자리 확보
        try:
            b = mini_in.get_node_bytes(e)
        except Exception:
            continue
        if len(b) > slot:
            b = shrink(b, slot)
            cut += 1
        else:
            fit += 1
        out[st:st + len(b)] = b
        for z in range(st + len(b), nxt):        # 남는 슬롯 널채움(압축 유리)
            out[z] = 0
    return bytes(out), fit, cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    src = open("DAT.BIN", "rb").read()
    sp = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    mini_ex = make_mini("tbl_all.json")
    mini_in = make_mini("tbl_full_kr.json")
    scenes = sorted(int(os.path.basename(f)[:-5]) for f in glob.glob("translation/*.json"))

    applied = skipped = err = 0
    strfit = strcut = 0
    done = []
    for n, sc in enumerate(scenes, 1):
        try:
            s = slot_of(bytes(src), sp, sc)
            if s is None:
                skipped += 1
                continue
            sb, se = s
            scont = bytes(src[sb:se])
            Path("work/_inp.bin").write_bytes(scont)
            scpk = Scpk.from_path(Path("work/_inp.bin"))
            orig = scpk.rsce
            if not orig or orig[:8] != b"THEIRSCE":
                skipped += 1
                continue
            mini_ex.id = 1
            Path("work/_inp.xml").write_bytes(
                mini_ex.get_xml_from_theirsce(Theirsce(orig), "Story"))
            data = json.load(open(f"translation/{sc}.json", encoding="utf-8"))
            inject_translation("work/_inp.xml", "work/_inpk.xml", data.get("lines", []))
            tree = etree.parse("work/_inpk.xml")
            root = tree.getroot()
            for e in root.findall(".//Speakers/Entry"):
                jt = e.find("JapaneseText")
                et = e.find("EnglishText")
                if jt is not None and et is not None and (jt.text or "") in NM:
                    et.text = NM[jt.text]
            tree.write("work/_inpk.xml", encoding="UTF-8", pretty_print=True)
            mini_in.id = 1
            new, f, c = build_inplace(orig, "work/_inpk.xml", mini_in)
            newc = swap_theirsce(scont, new, scpk._rsce_comp_type, comptolib)
            d = slot_of(bytes(dat), dp, sc)
            if d is None:
                skipped += 1
                continue
            db, de = d
            nr = 0
            q = de
            while q < len(dat) and dat[q] == 0 and nr < 8192:
                nr += 1
                q += 1
            safe = (de - db) + nr
            if len(newc) <= safe:
                if not args.check:
                    dat[db:db + safe] = newc + b"\x00" * (safe - len(newc))
                applied += 1
                strfit += f
                strcut += c
                done.append(sc)
            else:
                skipped += 1
        except Exception:
            err += 1
        if n % 100 == 0:
            print(f"  [{n}/{len(scenes)}] 적용 {applied} / 스킵 {skipped} / 에러 {err}", flush=True)

    print(f"\n[{'검사' if args.check else '적용'}] 제자리교체 씬 {applied} / 공간부족 스킵 {skipped} / 에러 {err}")
    print(f"  문자열: 슬롯적합 {strfit} / 축약 {strcut}")
    json.dump(done, open("work/speakers_jp/_inplace_done.json", "w"), indent=0)
    if not args.check and applied:
        open("DAT_jp_final.BIN", "wb").write(bytes(dat))
        print("[OK] DAT_jp_final 제자리교체 적용 (크기불변)")


if __name__ == "__main__":
    main()
