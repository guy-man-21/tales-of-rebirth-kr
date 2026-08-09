#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 월드맵/항해맵 모듈 하단바 버튼 라벨 한글화 (2026-08-02).
#  항해 컷씬 '스킵', 프리 십/샤오룬 타기·내리기, 인양 버튼.
#  ★★게임이 실제로 읽는 소스 = "압축 사본" 슬롯4164(+쌍둥이 16203) [comptolib type3,
#    블롭 머리가 ptrs[4164]-0x21 = 0x121f7200 / 0x3aa43400, 총 199,775B, 해제 732,176B
#    (원시 파일 대비 +0x30 레코드 프리픽스)]. PPSSPP SCEIO 로그로 실측 확정.
#    원시 사본(슬롯4163/16202, rel 0xA928A 등)은 게임이 안 읽는 죽은 사본이지만 함께 패치.
#  구조: [<0D>3X 버튼코드][00 00 00][20][라벨][00 00...] - 라벨만 kr+공백 정확 jplen,
#  널/버튼코드 불변. idempotent(원본 JP 바이트 또는 기적용 kr 검증 후 기록).
#  ★CN 도 이 모듈 미번역(오라클 없음) - 버튼코드 프리픽스가 표시 라벨임을 보증.
#  사용: py work\menu_jp\_worldmap_btn.py [--check] [--dat DAT_jp_final.BIN]
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, r"D:\PythonLib")

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TKR = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
INVK = {v: int(k, 16) for k, v in TKR.items()}
PTR = 0x126F90
SLOTS = (4163, 16202)

# (rel, jp_hex, kr) — jp_hex = 원본 라벨 바이트(길이 = 슬롯길이)
ITEMS = [
    (0x776E2, "9a6e9a8499a29a4f9a5b9a7099cde35e99ed", "프리십 타기"),      # フリーシップに乗る
    (0x776FE, "9a4f9a7c9a429a8599a29a8d99cde35e99ed", "샤오룬 타기"),       # シャオルーンに乗る
    (0x7B71A, "9a4f9a7c9a429a8599a29a8d99f4e0b199ec99ed", "샤오룬 내리기"),  # シャオルーンを降りる
    (0x7F85A, "9a6e9a8499a29a4f9a5b9a7099f4e0b199ec99ed", "프리십 내리기"),  # フリーシップを降りる
    (0x7F876, "9c6999afeaa499b499ed", "인양하기"),                          # 引き揚げる
    (0xA928A, "9a519a459a5b9a70", "스킵"),                                  # スキップ
]


PREV_KR = {  # 표기 변경 시 이전 한글 라벨도 패치 소스로 허용
    "프리십 타기": ["프리 십 타기"],
    "프리십 내리기": ["프리 십 내리기"],
}


def sources(jp, kr, L):
    """패치 소스로 인정할 바이트열(JP 원본 + 이전 한글 표기)."""
    out = [jp]
    for prev in PREV_KR.get(kr, []):
        e = enc(prev)
        if len(e) <= L:
            out.append(e + b" " * (L - len(e)))
    return out


def enc(kr):
    o = bytearray()
    for c in kr:
        if ord(c) < 0x80:
            o.append(ord(c))
        else:
            o += struct.pack(">H", INVK[c])
    return bytes(o)


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


# 압축 사본 (실소스): 블롭 절대 오프셋 (ptrs[슬롯]-0x21, 총 199775B)
COMP_BLOBS = (0x121F7200, 0x3AA43400)
COMP_TOT = 199775


def patch_compressed(dat, check):
    """슬롯4164/16203 압축 모듈 해제 -> 라벨 패치 -> type3 재압축 -> 제자리."""
    from pythonlib.utils import comptolib
    blob = bytes(dat[COMP_BLOBS[0]:COMP_BLOBS[0] + COMP_TOT])
    assert blob[0] == 3, "blob type"
    ds = struct.unpack_from("<I", blob, 5)[0]
    raw = bytearray(comptolib.decompress_data(blob))
    assert len(raw) == ds
    n = 0
    for rel, jph, kr in ITEMS:
        jp = bytes.fromhex(jph)
        L = len(jp)
        e = enc(kr)
        new = e + b" " * (L - len(e))
        i = -1
        for src in sources(jp, kr, L):
            i = raw.find(src)
            if i >= 0:
                break
        if i < 0:
            if raw.find(new) >= 0:
                continue  # 기적용
            print(f"[SKIP-COMP] {kr}: 원본/기적용 모두 불일치")
            continue
        assert raw[i - 1] == 0x20 and raw[i + L] == 0, hex(i)
        raw[i:i + L] = new
        n += 1
    if n and not check:
        nb = comptolib.compress_data(bytes(raw), version=3)
        assert comptolib.decompress_data(nb) == bytes(raw)
        assert len(nb) <= COMP_TOT, f"압축 초과 +{len(nb)-COMP_TOT}B"
        out = nb + b"\x00" * (COMP_TOT - len(nb))
        for b in COMP_BLOBS:
            dat[b:b + COMP_TOT] = out
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    args = ap.parse_args()
    dat = bytearray(open(args.dat, "rb").read())
    ptrs = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    n = 0
    for slot in SLOTS:
        base = ptrs[slot]
        for rel, jph, kr in ITEMS:
            jp = bytes.fromhex(jph)
            L = len(jp)
            cur = bytes(dat[base + rel:base + rel + L])
            e = enc(kr)
            assert len(e) <= L, (hex(rel), kr)
            new = e + b" " * (L - len(e))
            if cur == new:
                continue  # 기적용
            if cur not in sources(jp, kr, L):
                print(f"[SKIP] slot{slot}+{rel:#x}: 원본 불일치 {cur.hex()}")
                continue
            # 가드: 라벨 앞 = 20(공백), 뒤 = 널
            assert dat[base + rel - 1] == 0x20 and dat[base + rel + L] == 0, hex(rel)
            if not args.check:
                dat[base + rel:base + rel + L] = new
            n += 1
    nc = patch_compressed(dat, args.check)
    print(f"[{'검사' if args.check else '적용'}] 원시 {n}건 (슬롯 {SLOTS}) + 압축사본 {nc}건")
    if not args.check and (n or nc):
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 크기불변 {len(dat)}B")


if __name__ == "__main__":
    main()
