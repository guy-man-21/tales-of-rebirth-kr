#!/usr/bin/env python3
# 줄거리(슬롯3969) '전체 띄어쓰기' — CN 방식 복제: ★무압축 원시 저장 + repack 성장 (2026-07-18).
#  ★근거: CN판 실측 — 슬롯3969=33,184B(2배 성장, 원시/무압축, ptr+0 시작·퀴크 없음),
#    슬롯3970=1,847B(역시 원시화). CN 은 이 상태로 배틀 정상 = 성장/이동 자체는 안전.
#  ★이전 grow(압축 17,488B) 크래시의 정합적 설명: 게임의 '압축 해제 스테이징 버퍼'가 원본
#    압축크기(16,608B) 기준 고정 -> 압축본이 커지면 인접 리소스(배틀결과 포인터) 오염.
#    원시 저장은 스테이징을 안 거침 -> CN 이 원시로 우회한 이유.
#  레이아웃:
#    new3968 = 원본3968[:1024] + 32널  (꼬리의 구 압축헤더 제거 - 로더 오검출 방지)
#    new3969 = 원시블롭(헤더+조각, 전체 띄어쓰기) + 널패딩 -> 33,184B (CN 과 동일)
#    new3970 = 슬롯3970 원시해제본(1,838B) + 널패딩 -> 3,008B (총 delta 18,432 = 2048x9)
#  사용: py work\synopsis_jp\_grow_raw.py [--check] -> DAT_jp_growraw.BIN + EBOOT_jp_growraw.BIN
import argparse
import json
import os
import re
import struct
import subprocess
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
TAG = re.compile(r"<([0-9A-Fa-f]{2})>")
PTR = 0x126F90
HDR = 0xB14
N69 = 33184          # CN 과 동일
N70 = 3008           # 1838 원시 + 패딩 (총 delta 18432 = 2048x9)


def enc_kr(kr):
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
        elif ord(c) < 0x80:
            out.append(ord(c))
        else:
            return None
        i += 1
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
    args = ap.parse_args()

    src = open("DAT.BIN", "rb").read()
    sp = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    lo = sp[3969] - 32
    csz0 = struct.unpack_from("<I", src, lo + 1)[0]
    d = comptolib.decompress_data(bytes(src[lo:lo + 9 + csz0]))

    # 전체 띄어쓰기 블롭 (필터 없음 - 에이전트 공백 전부)
    rows = json.load(open("work/synopsis_jp/synopsis_work_full.json", encoding="utf-8"))
    krmap = {}
    nsp = 0
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr:
            continue
        nsp += kr.count(" ")
        e = enc_kr(kr)
        if e is not None:
            krmap[r["off"]] = e
    out = bytearray(d[:HDR])
    remap = {}
    i = HDR
    while i < len(d):
        if d[i] == 0:
            st = i
            while i < len(d) and d[i] == 0:
                i += 1
            out += b"\x00" * (i - st)          # 널런 원본 그대로
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
    blob = bytes(out)
    print(f"[블롭] 원시 {len(blob)}B (공백 {nsp}, 헤더 {hits}) -> 슬롯 {N69}B")
    if len(blob) > N69:
        print("[중단] N69 초과")
        return

    # 슬롯3970 원시화
    lo70 = sp[3970] - 16
    c70 = struct.unpack_from("<I", src, lo70 + 1)[0]
    d70 = comptolib.decompress_data(bytes(src[lo70:lo70 + 9 + c70]))
    print(f"[3970] 원시 {len(d70)}B -> 슬롯 {N70}B")
    if len(d70) > N70:
        print("[중단] N70 초과")
        return

    # 슬롯 파일
    s68 = src[sp[3968]:sp[3969]]
    new68 = s68[:1024] + b"\x00" * (len(s68) - 1024)     # 꼬리 구 압축헤더 제거
    new69 = blob + b"\x00" * (N69 - len(blob))
    new70 = bytes(d70) + b"\x00" * (N70 - len(d70))
    delta = (len(new69) - (sp[3970] - sp[3969])) + (len(new70) - (sp[3971] - sp[3970]))
    print(f"[슬롯] 3968 {len(new68)}B(크기불변) / 3969 {len(new69)}B / 3970 {len(new70)}B "
          f"/ 총 delta {delta:+d} (2048배수 {delta % 2048 == 0})")
    assert delta % 2048 == 0

    if args.check:
        return
    open("work/synopsis_jp/_r3968.bin", "wb").write(new68)
    open("work/synopsis_jp/_r3969.bin", "wb").write(new69)
    open("work/synopsis_jp/_r3970.bin", "wb").write(new70)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "repack_psp_dat.py",
                        "--eboot", "EBOOT_jp_new.BIN", "--dat", "DAT_jp_final.BIN",
                        "--replace", "3968:work/synopsis_jp/_r3968.bin",
                        "--replace", "3969:work/synopsis_jp/_r3969.bin",
                        "--replace", "3970:work/synopsis_jp/_r3970.bin",
                        "--out-dat", "DAT_jp_growraw.BIN", "--out-eboot", "EBOOT_jp_growraw.BIN"],
                       env=env)
    if r.returncode == 0:
        print("[OK] DAT_jp_growraw.BIN + EBOOT_jp_growraw.BIN (실기검증 후 승격)")


if __name__ == "__main__":
    main()
