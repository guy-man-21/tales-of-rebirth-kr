#!/usr/bin/env python3
# 줄거리 블롭 '컴팩트' 재구성: 조각을 패딩 없이 이어붙이고(널런 길이는 원본 그대로 복제),
#  헤더(0~0xb14) 안의 조각시작 포인터를 재매핑. 결과 재압축 크기 측정.
#  사용: py work\synopsis_jp\_compact.py [--out blob.bin]
import argparse
import json
import os
import re
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
sys.path.insert(0, ".")
from pythonlib.utils import comptolib

Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
TAG = re.compile(r"<([0-9A-Fa-f]{2})>")
PTR = 0x126F90
SLOT = 3969
HDR = 0xB14


def enc(kr):
    out = bytearray()
    i = 0
    while i < len(kr):
        m = TAG.match(kr, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        c = kr[i]
        if c in inv:
            out += struct.pack(">H", inv[c])
            i += 1
        elif ord(c) < 0x80:
            out.append(ord(c))
            i += 1
        else:
            return None
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    src = open("DAT.BIN", "rb").read()
    eb = open("ULJS00132_EBOOT.BIN", "rb").read()
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > len(src) * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    # 원본 블롭 해제
    lo = p[SLOT] - 32
    csz = struct.unpack_from("<I", src, lo + 1)[0]
    ctype = src[lo]
    d = comptolib.decompress_data(bytes(src[lo:lo + 9 + csz]))
    print(f"원본 해제 {len(d)}B, csize {csz}")

    # 번역 로드 (off -> kr_bytes)
    rows = json.load(open("work/synopsis_jp/synopsis_work.json", encoding="utf-8"))
    krmap = {}
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if kr:
            e = enc(kr)
            if e is not None:
                krmap[r["off"]] = e

    # 문자열영역 워크: 조각/널런 시퀀스
    out = bytearray(d[:HDR])
    remap = {}
    i = HDR
    n_frag = n_kr = 0
    while i < len(d):
        if d[i] == 0:
            run = 0
            while i < len(d) and d[i] == 0:
                run += 1
                i += 1
            out += b"\x00" * run          # 널런 길이 원본 그대로
            continue
        st = i
        while i < len(d) and d[i] != 0:
            i += 2 if d[i] >= 0x81 else 1
        frag = bytes(d[st:i])
        remap[st] = len(out)
        n_frag += 1
        if st in krmap:
            out += krmap[st]              # 패딩 없이 한글
            n_kr += 1
        else:
            out += frag                    # 비번역/제어 조각은 원본
    print(f"조각 {n_frag} (한글 {n_kr}) / 새 해제크기 {len(out)}B (원본 {len(d)}, -{len(d)-len(out)})")

    # 헤더 포인터 재매핑
    hits = miss = 0
    anomalies = []
    for off in range(0, HDR, 4):
        v = struct.unpack_from("<I", out, off)[0]
        if HDR <= v < len(d):
            if v in remap:
                struct.pack_into("<I", out, off, remap[v])
                hits += 1
            else:
                miss += 1
                if len(anomalies) < 10:
                    anomalies.append((off, v))
    print(f"헤더 재매핑: {hits}개 / 조각시작 아님 {miss}개")
    for off, v in anomalies:
        print(f"  [주의] 헤더@{off:#x} -> {v:#x} (조각시작 아님, 미변경)")

    comp = comptolib.compress_data(bytes(out), version=ctype)
    print(f"재압축: {len(comp)}B (목표 <=16608, 초과 {max(0,len(comp)-16608)})")
    if args.out:
        open(args.out, "wb").write(bytes(out))
        print(f"[OK] 해제블롭 저장 -> {args.out}")


if __name__ == "__main__":
    main()
