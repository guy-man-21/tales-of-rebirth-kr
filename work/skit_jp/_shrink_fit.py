#!/usr/bin/env python3
# 초과 슬롯만 대상으로: 재압축 footprint 초과분을 '무손실~저손실 축약'으로 맞춘다.
#  slot별로 PAK2 재조립->재압축 측정. 초과면 SHRINK 변환 단계적 적용 후 재측정.
#  맞으면 skits/{slot}.json 의 kr 갱신. 못 맞추면 잔여 리포트.
#  orig_len 은 --dst(스킷 패치 전 클린 DAT)에서 읽는다(재빌드 함정 회피).
#  사용: py work\skit_jp\_shrink_fit.py [--dst DAT_jp_final_preskit.BIN] [--apply]
import argparse
import glob
import json
import os
import re
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
TAG = re.compile(r"<[^>]+>")


def read_ptrs(eb, dsize):
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > dsize * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    return p


def find_pak(buf, lo):
    for delta in range(-64, 9):
        o = lo + delta
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


# --- 저손실 축약 규칙 (구어체 보존, 태그 밖에서만) ---
# 순서 중요: 긴 것 먼저. 의미 보존 위주.
SUBS = [
    ("　", " "),          # 전각공백 -> 반각(2B->1B)
    ("무엇을", "뭘"), ("무엇", "뭐"),
    ("이것은", "이건"), ("이것이", "이게"), ("이것", "이거"),
    ("그것은", "그건"), ("그것이", "그게"), ("그것", "그거"),
    ("저것은", "저건"), ("저것이", "저게"), ("저것", "저거"),
    ("것입니다", "겁니다"), ("것이다", "거다"), ("것이야", "거야"),
    ("것이", "게"), ("것을", "걸"), ("것은", "건"),
    ("무슨 일이야", "무슨 일이야"),
    ("하지 않으면", "안 하면"),
    ("때문에", "탓에"),
    ("그리고 ", ""), ("하지만 ", "다만 "),
    ("정말로", "정말"), ("완전히", "완전"), ("역시나", "역시"),
    ("~라고 ", "~고 "),
    ("해야 한다", "해야 해"), ("해야만 한다", "해야 해"),
    ("있는 것 같다", "있는 듯"), ("인 것 같다", "인 듯"),
]
SPACE_MULTI = re.compile(r"  +")
SPACE_BEFORE_PUNC = re.compile(r"\s+([!?,.…])")


def shrink_text(kr, level):
    # 태그 보호: 태그를 자리표시자로 빼고 축약 후 복원
    tags = []
    def stash(m):
        tags.append(m.group(0)); return f"\x00{len(tags)-1}\x00"
    s = TAG.sub(stash, kr)
    # level0: 공백류만 (무손실)
    s = s.replace("　", " ")
    s = SPACE_MULTI.sub(" ", s)
    s = SPACE_BEFORE_PUNC.sub(r"\1", s)
    s = re.sub(r"[ ]+(\n)", r"\1", s)   # 후행공백
    s = re.sub(r"(\n)[ ]+", r"\1", s)   # 선행공백
    s = s.strip(" ")
    if level >= 1:
        for a, b in SUBS[1:]:            # 어휘 축약(전각공백은 위에서 처리)
            s = s.replace(a, b)
        s = SPACE_MULTI.sub(" ", s)
    # 태그 복원
    def restore(m):
        return tags[int(m.group(1))]
    s = re.sub(r"\x00(\d+)\x00", restore, s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dst", default="DAT_jp_final_preskit.BIN")
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    ap.add_argument("--apply", action="store_true", help="맞은 슬롯 kr 을 실제로 갱신")
    ap.add_argument("--slots", default="", help="쉼표구분 슬롯. 없으면 전체 스캔")
    args = ap.parse_args()

    src = open("DAT.BIN", "rb").read()
    src_ptrs = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    dat = open(args.dst, "rb").read()
    ptrs = read_ptrs(open(args.eboot, "rb").read(), len(dat))

    mex = make_mini("tbl_all.json"); mex.id = 1
    min_ = make_mini("tbl_full_kr.json"); min_.id = 1
    tmp = "work/skit_jp/_sx.xml"; tmpk = "work/skit_jp/_sxKR.xml"

    def measure(slot, lines):
        rs = find_pak(src, src_ptrs[slot])
        rd = find_pak(dat, ptrs[slot])
        if rs is None or rd is None:
            return None, None
        _, _, pak, ctype = rs
        _, orig_len, _, _ = rd
        data = pak2lib.get_data(pak)
        rsce = data.chunks.theirsce
        mex.id = 1
        Path(tmp).write_bytes(mex.get_xml_from_theirsce(Theirsce(rsce), "Story"))
        inject_translation(tmp, tmpk, lines, field="EnglishText")
        min_.id = 1
        nt = min_.get_new_theirsce(Theirsce(rsce), Path(tmpk)); nt.seek(0)
        data.chunks.theirsce = nt.read()
        comp = comptolib.compress_data(pak2lib.create_pak2(data), version=ctype)
        return len(comp), orig_len

    if args.slots:
        slots = [int(x) for x in args.slots.split(",")]
    else:
        slots = sorted(int(os.path.basename(p)[:-5]) for p in glob.glob("work/skit_jp/skits/*.json"))

    fixed = still = 0
    still_list = []
    for slot in slots:
        p = f"work/skit_jp/skits/{slot}.json"
        js = json.load(open(p, encoding="utf-8"))
        lines = [l for l in js["lines"] if (l.get("kr") or "").strip()]
        if not lines:
            continue
        cl, ol = measure(slot, lines)
        if cl is None or cl <= ol:
            continue   # 안 초과
        # 초과 -> level0(공백) 시도, 그다음 level1(어휘)
        orig_kr = {l["id"]: l.get("kr", "") for l in js["lines"]}
        done = False
        for level in (0, 1):
            for l in js["lines"]:
                if (l.get("kr") or "").strip():
                    l["kr"] = shrink_text(orig_kr[l["id"]], level)
            lines2 = [l for l in js["lines"] if (l.get("kr") or "").strip()]
            cl2, ol2 = measure(slot, lines2)
            if cl2 <= ol2:
                fixed += 1
                done = True
                if args.apply:
                    json.dump(js, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                break
        if not done:
            still += 1
            still_list.append((slot, cl2 - ol2))
            # 원복 (apply 아니어도 메모리만이라 무관)
            for l in js["lines"]:
                if l["id"] in orig_kr:
                    l["kr"] = orig_kr[l["id"]]

    print(f"[shrink] 맞춤 {fixed} / 잔여 {still}  (apply={args.apply})")
    for slot, d in sorted(still_list, key=lambda x: -x[1])[:60]:
        print(f"  슬롯 {slot}: 잔여 +{d}")


if __name__ == "__main__":
    main()
