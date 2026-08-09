#!/usr/bin/env python3
# 줄거리(슬롯3969) 전체 띄어쓰기 = CN 방식 완전복제 (2026-07-18).
#  ★핵심규명: JP/CN EBOOT 코드 diff = 단 8바이트 (file 0x15ce8~0x15cf0 = vaddr 0x8818ce8).
#    이 함수 = 해제 디스패처 decompress(dst,src,dsize). src[0]=타입(1/0/3=압축, 10=특수).
#    JP: 타입!=10 이면 return(에러). CN: 타입!=10 이면 raw 복사경로(0x8818d0c)로 진입.
#    => CN 은 슬롯3969 를 '압축 안 하고 해제상태(0x0b14헤더+조각) 그대로' 저장(첫바이트 0x14),
#       패치된 로더가 raw 로 읽음. 실측: CN 슬롯3969=raw 33216B, 배틀정상.
#  ★내 이전 growraw 실패원인 2개 모두 수정: (1)EBOOT 패치 적용 (2)±32 퀴크 레이아웃 준수.
#  레이아웃(퀴크 보존, _grow_build 와 동일):
#    new3968 = 원본3968[:-32] + rawblob[:32]      (블롭 머리 32B는 3968 꼬리)
#    new3969 = rawblob[32:] + 널갭 + 원본3969末16B (슬롯3970 압축블롭 머리 보존)
#  사용: py work\synopsis_jp\_grow_cn.py [--check] -> DAT_jp_growcn.BIN + EBOOT_jp_growcn.BIN
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
SECTOR = 2048
# CN 8바이트 패치 (JP EBOOT 파일 오프셋). ★명령어는 u32 리틀엔디언으로 기록!
#  (빅엔디언 실수 시 bne 가 j 0x18854 로 해석 -> 스토리북 열자마자 Bad Execution Address 실증)
PATCH = {0x15CE8: struct.pack("<I", 0x15620008),   # bne t3,v0,0x8818d0c
         0x15CEC: struct.pack("<I", 0x26060009)}   # addiu a2,s0,9


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

    # 전체 띄어쓰기 raw 블롭 (필터 없음)
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
            out += b"\x00" * (i - st)
            continue
        st = i
        while i < len(d) and d[i] != 0:
            i += 2 if d[i] >= 0x81 else 1
        remap[st] = len(out)
        out += krmap.get(st, bytes(d[st:i]))
    for off in range(0, HDR, 4):
        v = struct.unpack_from("<I", out, off)[0]
        if HDR <= v < len(d) and v in remap:
            struct.pack_into("<I", out, off, remap[v])
    rawblob = bytes(out)                      # 압축 안 함 (CN 방식)
    print(f"[raw블롭] {len(rawblob)}B (공백 {nsp}), 첫바이트 {rawblob[0]:#x} (0x14=raw경로 라우팅)")

    # 퀴크 레이아웃
    old68 = src[sp[3968]:sp[3969]]
    old69 = src[sp[3969]:sp[3970]]
    old69_len = len(old69)
    new68 = old68[:-32] + rawblob[:32]
    body = rawblob[32:] + b"\x00" * 32
    tail16 = old69[-16:]
    base_len = len(body) + 16
    pad = (-(base_len - old69_len)) % SECTOR
    new69 = body + b"\x00" * pad + tail16
    delta = len(new69) - old69_len
    print(f"[슬롯] 3968 {len(new68)}B(불변) / 3969 {len(new69)}B (delta {delta:+d}, 2048배수 {delta % SECTOR == 0})")
    assert len(new68) == len(old68) and delta % SECTOR == 0

    if args.check:
        # EBOOT 패치 대상 확인
        eb = open("EBOOT_jp_new.BIN", "rb").read()
        for off, val in PATCH.items():
            print(f"  패치 @{off:#x}: 현재 {eb[off:off+4].hex()} -> {val.hex()}")
        return

    open("work/synopsis_jp/_cn3968.bin", "wb").write(new68)
    open("work/synopsis_jp/_cn3969.bin", "wb").write(new69)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "repack_psp_dat.py",
                        "--eboot", "EBOOT_jp_new.BIN", "--dat", "DAT_jp_final.BIN",
                        "--replace", "3968:work/synopsis_jp/_cn3968.bin",
                        "--replace", "3969:work/synopsis_jp/_cn3969.bin",
                        "--out-dat", "DAT_jp_growcn.BIN", "--out-eboot", "EBOOT_jp_growcn.BIN"],
                       env=env)
    if r.returncode != 0:
        print("[중단] repack 실패")
        return
    # EBOOT 8바이트 패치 적용
    eb = bytearray(open("EBOOT_jp_growcn.BIN", "rb").read())
    for off, val in PATCH.items():
        eb[off:off + 4] = val
    open("EBOOT_jp_growcn.BIN", "wb").write(bytes(eb))
    print(f"[OK] DAT_jp_growcn.BIN + EBOOT_jp_growcn.BIN (CN 8바이트 패치 적용) — 실기검증 후 승격")


if __name__ == "__main__":
    main()
