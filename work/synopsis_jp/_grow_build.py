#!/usr/bin/env python3
# 줄거리(슬롯3969) '띄어쓰기 복원판' 성장 빌드 (2026-07-18).
#  1) scratchpad space_*_spaced.json 병합 -> synopsis_work_full.json (kr 갱신)
#  2) 컴팩트 블롭(조각 패킹+헤더포인터 재매핑, 널런 보존) -> 재압축 NB
#  3) 슬롯 교체파일 생성 (★퀴크 보존):
#       new3968 = src3968[:-32] + NB[:32]          (블롭 머리 32B는 3968 꼬리에)
#       new3969 = NB[32:] + 널패딩 + src3969末16B   (3970 블롭 머리 16B 보존,
#                 패딩은 성장분이 2048 배수가 되도록 산출)
#  4) repack_psp_dat 로 전체 재조립 (입력 = 현행 DAT_jp_final + EBOOT_jp_new 짝).
#  ★이전 '슬롯3969 성장=배틀크래시' 결론은 메뉴 널채움 크래시(동일 PC)와 교락 — 재검증 목적.
#  사용: py work\synopsis_jp\_grow_build.py [--check] [--no-repack]
import argparse
import glob
import json
import os
import re
import struct
import subprocess
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
SECTOR = 2048
SP = r"C:\Users\home\AppData\Local\Temp\claude\D--clean-project\2c73b695-ce85-4fd0-b460-f5b3c22a422e\scratchpad"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-repack", action="store_true")
    args = ap.parse_args()

    # 1) 병합
    rows = json.load(open("work/synopsis_jp/synopsis_work_full.json", encoding="utf-8"))
    rmap = {r["off"]: r for r in rows}
    merged = 0
    for f in sorted(glob.glob(os.path.join(SP, "space_*_spaced.json"))):
        for s in json.load(open(f, encoding="utf-8")):
            r = rmap.get(s["off"])
            ns = (s.get("kr") or "").strip()
            if r and ns:
                # 안전: 공백 제거하면 기존과 동일해야 (글자 변경 금지 검증)
                if ns.replace(" ", "") != (r.get("kr") or "").replace(" ", ""):
                    print(f"  [경고] off {r['off']:#x}: 공백 외 변경 감지 -> 스킵")
                    continue
                r["kr"] = ns
                merged += 1
    print(f"[병합] 띄어쓰기 반영 {merged}조각")
    json.dump(rows, open("work/synopsis_jp/synopsis_work_full.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 2) 컴팩트 블롭 (조각 패킹 + 헤더 재매핑)
    src = open("DAT.BIN", "rb").read()
    sp_ = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    lo = sp_[SLOT] - 32
    csz = struct.unpack_from("<I", src, lo + 1)[0]
    ctype = src[lo]
    d = comptolib.decompress_data(bytes(src[lo:lo + 9 + csz]))
    krmap = {}
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if kr:
            e = enc(kr)
            if e is not None:
                krmap[r["off"]] = e
    out = bytearray(d[:HDR])
    remap = {}
    i = HDR
    while i < len(d):
        if d[i] == 0:
            run = 0
            while i < len(d) and d[i] == 0:
                run += 1
                i += 1
            out += b"\x00" * run
            continue
        st = i
        while i < len(d) and d[i] != 0:
            i += 2 if d[i] >= 0x81 else 1
        remap[st] = len(out)
        out += krmap.get(st, bytes(d[st:i]))
    hits = 0
    for off in range(0, HDR, 4):
        v = struct.unpack_from("<I", out, off)[0]
        if HDR <= v < len(d) and v in remap:
            struct.pack_into("<I", out, off, remap[v])
            hits += 1
    NB = comptolib.compress_data(bytes(out), version=ctype)
    if comptolib.decompress_data(NB) != bytes(out):
        print("[중단] roundtrip 불일치")
        return
    print(f"[블롭] 해제 {len(out)}B / 재압축 {len(NB)}B (원본 footprint 16608, "
          f"{'제자리 가능!' if len(NB) <= 16608 else '성장 필요 +%d' % (len(NB) - 16608)}) / 헤더 {hits}")

    # 3) 슬롯 교체파일
    s68, s69, s70 = sp_[3968], sp_[SLOT], sp_[SLOT + 1]
    old68 = src[s68:s69]
    old69 = src[s69:s70]
    old69_len = len(old69)
    new68 = old68[:-32] + NB[:32]
    body = NB[32:] + b"\x00" * 32              # 원본처럼 갭 확보
    tail16 = old69[-16:]                       # 3970 블롭 머리 16B
    base_len = len(body) + 16
    pad = (-(base_len - old69_len)) % SECTOR
    new69 = body + b"\x00" * pad + tail16
    delta = len(new69) - old69_len
    print(f"[슬롯] new3968 {len(new68)}B(불변) / new3969 {len(new69)}B (delta {delta:+d}, "
          f"2048배수 {delta % SECTOR == 0})")
    assert len(new68) == len(old68) and delta % SECTOR == 0

    if args.check:
        return
    open("work/synopsis_jp/_new3968.bin", "wb").write(new68)
    open("work/synopsis_jp/_new3969.bin", "wb").write(new69)

    if args.no_repack:
        print("[OK] 슬롯파일 생성 완료 (repack 생략)")
        return
    # 4) repack (현행 최종본 짝 입력 -> _grow 산출)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "repack_psp_dat.py",
                        "--eboot", "EBOOT_jp_new.BIN", "--dat", "DAT_jp_final.BIN",
                        "--replace", "3968:work/synopsis_jp/_new3968.bin",
                        "--replace", "3969:work/synopsis_jp/_new3969.bin",
                        "--out-dat", "DAT_jp_grow.BIN", "--out-eboot", "EBOOT_jp_grow.BIN"],
                       env=env)
    if r.returncode == 0:
        print("[OK] DAT_jp_grow.BIN + EBOOT_jp_grow.BIN 생성 (실기검증 후 최종 승격)")


if __name__ == "__main__":
    main()
