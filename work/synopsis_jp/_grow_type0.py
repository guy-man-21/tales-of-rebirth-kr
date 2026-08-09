#!/usr/bin/env python3
# 줄거리(슬롯3969) 전체 띄어쓰기 = CN 레이아웃 완전복제: ★type0(무압축 저장) (2026-07-18 최종).
#  ★CN 실측 해독:
#    - CN 헤더 @ptr3969-41: [00][csize=33166][dsize=33166] = comptolib type0 = 저장(무압축).
#      type0 은 JP 순정 디스패처(0x8818c28)가 memcpy(0x88145e8->0x88c8c8c)로 처리 = 코드패치 불필요!
#    - CN 슬롯3968 = 1065B (+9) = [고유데이터 1024][9B 헤더][raw 첫 32B] -> raw 본체가 ptr-32 에 위치
#      (퀴크 유지). CN 슬롯3969 = raw 나머지+패딩. CN 배틀 정상 = 이 방식 검증됨.
#    - CN 의 8바이트 디스패처 패치(0x15CE8)는 다른 리소스용 -> 우리는 미적용(EBOOT 코드 무변경).
#  레이아웃:
#    new3968(1065B) = 원본3968[:1024] + [00][csize][dsize] + raw[:32]
#    new3969        = raw[32:] + 널패딩 + 원본3969末16B(슬롯3970 압축헤드 보존)
#    총 delta(+9 포함) 2048 배수.
#  사용: py work\synopsis_jp\_grow_type0.py [--check] -> DAT_jp_growt0.BIN + EBOOT_jp_growt0.BIN
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
    raw = bytes(out)
    hdr9 = struct.pack("<bLL", 0, len(raw), len(raw))    # type0, csize=dsize=len
    print(f"[raw] {len(raw)}B (공백 {nsp}) / 헤더 type0 {len(raw)}/{len(raw)}")

    old68 = src[sp[3968]:sp[3969]]
    old69 = src[sp[3969]:sp[3970]]
    new68 = old68[:1024] + hdr9 + raw[:32]               # 1024+9+32 = 1065 (CN 동일)
    body = raw[32:]
    tail16 = old69[-16:]
    # 총 delta = (len(new68)-1056) + (n69-16624) ≡ 0 (mod 2048)
    d68 = len(new68) - len(old68)
    base_len = len(body) + 16
    pad = (-(d68 + base_len - len(old69))) % SECTOR
    new69 = body + b"\x00" * pad + tail16
    delta = d68 + len(new69) - len(old69)
    print(f"[슬롯] 3968 {len(new68)}B ({d68:+d}) / 3969 {len(new69)}B / 총 delta {delta:+d} "
          f"(2048배수 {delta % SECTOR == 0})")
    assert delta % SECTOR == 0

    if args.check:
        return
    open("work/synopsis_jp/_t3968.bin", "wb").write(new68)
    open("work/synopsis_jp/_t3969.bin", "wb").write(new69)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "repack_psp_dat.py",
                        "--eboot", "EBOOT_jp_new.BIN", "--dat", "DAT_jp_final.BIN",
                        "--replace", "3968:work/synopsis_jp/_t3968.bin",
                        "--replace", "3969:work/synopsis_jp/_t3969.bin",
                        "--out-dat", "DAT_jp_growt0.BIN", "--out-eboot", "EBOOT_jp_growt0.BIN"],
                       env=env)
    if r.returncode == 0:
        print("[OK] DAT_jp_growt0.BIN + EBOOT_jp_growt0.BIN (코드 무변경, type0 저장)")


if __name__ == "__main__":
    main()
