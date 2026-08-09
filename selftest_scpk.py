#!/usr/bin/env python3
# ============================================================
#  selftest_scpk.py -- 컨테이너 해석이 맞는지 바이트단위로 증명
#
#  원본 THEIRSCE 를 그대로 다시 끼워넣으면 원본 슬롯이 '바이트단위로' 복원되어야 한다.
#  하나라도 어긋나면 그 씬의 컨테이너 해석(SCPK base / 블롭 경계 / 크기테이블)이 틀린 것이고,
#  그런 씬을 빌드하면 게임이 크래시한다.
#
#  사용: py selftest_scpk.py
# ============================================================
import struct
import sys
from pathlib import Path

sys.path.insert(0, ".")
from scpk_patch import build_slot, find_container  # noqa: E402

PTR = 0x126F90


def read_pointers(eboot, dat_size):
    ptrs, i = [], 0
    while True:
        v = struct.unpack_from("<I", eboot, PTR + i * 4)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size * 1.05):
            break
        ptrs.append(v)
        i += 1
        if i > 40000:
            break
    return ptrs


dat = Path("DAT_cn.BIN").read_bytes()
ptrs = read_pointers(Path("EBOOT_DEC.BIN").read_bytes(), len(dat))
scenes = sorted(int(p.stem) for p in Path("translation").glob("*.json")
                if p.stem.isdigit())

exact = []      # 원본 복원 일치
mism = []       # 불일치 (컨테이너 해석 틀림 -> 위험)
crossp = []     # 크기테이블이 슬롯 밖 (원본 복원 시엔 크기가 같으니 patch 없어야 정상)
err = []

for sc in scenes:
    try:
        c = find_container(dat, ptrs, sc)
        t = c["theirsce_off"]
        csize = struct.unpack_from("<I", dat, t - 8)[0]
        orig = dat[t:t + csize]
        out, patch, info = build_slot(dat, ptrs, sc, orig)
        same = out == dat[ptrs[sc]:ptrs[sc + 1]]
        if patch:
            crossp.append(sc)      # 원본 그대로인데 확장? -> 해석 이상
        if same and not patch:
            exact.append(sc)
        else:
            mism.append((sc, info, len(out), ptrs[sc + 1] - ptrs[sc]))
    except Exception as e:
        err.append((sc, f"{type(e).__name__}: {e}"))

print(f"[자기검증] 대상 {len(scenes)}씬")
print(f"  원본 바이트단위 복원: {len(exact)}")
print(f"  불일치(위험):        {len(mism)}")
print(f"  파싱 에러:           {len(err)}")
for sc, info, a, b in mism[:15]:
    print(f"    씬 {sc}: {info} (새 {a}B vs 원본 {b}B)")
for sc, why in err[:15]:
    print(f"    씬 {sc}: {why}")
