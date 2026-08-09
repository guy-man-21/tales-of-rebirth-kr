#!/usr/bin/env python3
# ============================================================
#  Tales of Rebirth PSP - DAT.BIN 재패킹 + EBOOT 포인터 갱신
#
#  특정 파일(예: #00014 폰트)을 교체하고, 파일 크기 변화에 맞춰
#  DAT.BIN을 재조립하고 EBOOT의 포인터 테이블(0x126F90)을 갱신.
#  (파일들은 정렬 패딩 없이 이어붙임 - 중국어판과 동일 방식)
#
#  메모리 절약: 바뀐 파일 앞부분은 그대로 복사, 뒷부분만 오프셋 이동.
#
#  사용법:
#    py repack_psp_dat.py --eboot ULJS00132_EBOOT.BIN --dat DAT.BIN \
#        --replace 14:00014_firstline.bin \
#        --out-dat DAT_new.BIN --out-eboot EBOOT_new.BIN
# ============================================================
import struct, argparse, shutil
from pathlib import Path

PTR = 0x126F90

def read_pointers(eboot, dat_size):
    ptrs = []
    i = 0
    while True:
        v = struct.unpack_from("<I", eboot, PTR + i*4)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size * 1.05):
            break
        ptrs.append(v); i += 1
        if i > 20000: break
    return ptrs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eboot", required=True, help="복호화된 EBOOT")
    ap.add_argument("--dat", required=True, help="원본 DAT.BIN")
    ap.add_argument("--replace", action="append", required=True,
                    help="'인덱스:새파일' (반복 가능). 예: 14:00014_firstline.bin")
    ap.add_argument("--out-dat", default="DAT_new.BIN")
    ap.add_argument("--out-eboot", default="EBOOT_new.BIN")
    args = ap.parse_args()

    eboot = bytearray(Path(args.eboot).read_bytes())
    dat_path = Path(args.dat)
    dat_size = dat_path.stat().st_size

    # 교체 목록 파싱
    repl = {}
    for r in args.replace:
        idx_s, fp = r.split(":", 1)
        repl[int(idx_s)] = Path(fp).read_bytes()
    print("교체 파일:", {k: len(v) for k, v in repl.items()})

    # === 2048(섹터) 정렬 패딩 ===
    # EBOOT 2차 테이블 값들이 전부 2048 정렬이다(스트리밍/모듈 로드용 추정).
    # 총 delta 가 2048 배수가 아니면 그 정렬이 깨져 Bad Execution Address 로 죽는다(실측).
    # -> 마지막 교체 파일에 널 패딩을 붙여 총 delta 를 2048 배수로 맞춘다.
    _tmp_eboot = Path(args.eboot).read_bytes()
    _tmp_size = dat_path.stat().st_size
    _p = read_pointers(bytearray(_tmp_eboot), _tmp_size)
    _delta = sum(len(v) - (_p[k+1] - _p[k]) for k, v in repl.items())
    _pad = (-_delta) % 2048
    if _pad:
        last = max(repl.keys())
        repl[last] = repl[last] + b"\x00" * _pad
        print(f"정렬 패딩: delta {_delta:+d} -> {_delta+_pad:+d} (슬롯{last}에 +{_pad}B)")

    ptrs = read_pointers(eboot, dat_size)
    n = len(ptrs) - 1
    print(f"파일 {n}개, 포인터 {len(ptrs)}개")

    # 교체는 연속되지 않을 수 있으나, 여기선 최소 인덱스부터 처리
    repl_idxs = sorted(repl.keys())
    first = repl_idxs[0]
    print(f"교체 최소 인덱스: #{first:05d}")

    # 새 포인터 계산 (원본 크기 -> 새 크기 반영, 누적 이동)
    old_sizes = [ptrs[i+1]-ptrs[i] for i in range(n)]
    new_sizes = list(old_sizes)
    for idx, data in repl.items():
        new_sizes[idx] = len(data)
    new_ptrs = [ptrs[0]]
    for i in range(n):
        new_ptrs.append(new_ptrs[-1] + new_sizes[i])

    print(f"원본 DAT 끝: 0x{ptrs[n]:X}, 새 DAT 끝: 0x{new_ptrs[n]:X} (차이 {new_ptrs[n]-ptrs[n]:+d})")

    # === DAT.BIN 재조립 (스트리밍) ===
    with open(dat_path, "rb") as fin, open(args.out_dat, "wb") as fout:
        # 헤더 + 첫 교체 이전 파일들: 바이트 [0 : ptrs[first]] 그대로 복사
        fin.seek(0)
        remaining = ptrs[first]
        while remaining > 0:
            chunk = fin.read(min(remaining, 8*1024*1024))
            if not chunk: break
            fout.write(chunk); remaining -= len(chunk)
        # 각 파일을 순서대로: 교체분은 새 데이터, 아니면 원본에서 복사
        for i in range(first, n):
            if i in repl:
                fout.write(repl[i])
            else:
                fin.seek(ptrs[i])
                rem = old_sizes[i]
                while rem > 0:
                    chunk = fin.read(min(rem, 8*1024*1024))
                    if not chunk: break
                    fout.write(chunk); rem -= len(chunk)
        # 원본 끝의 잔여 패딩 보존
        fin.seek(ptrs[n])
        tail = fin.read()
        if tail:
            fout.write(tail)
    print(f"DAT 재조립 완료 -> {args.out_dat}")

    # === EBOOT 1차 포인터 테이블 갱신 ===
    for i, p in enumerate(new_ptrs):
        struct.pack_into("<I", eboot, PTR + i*4, p)
    # 종료 마커(원래 0) 유지 확인
    struct.pack_into("<I", eboot, PTR + len(new_ptrs)*4, 0)
    print(f"EBOOT 1차 포인터 갱신 완료")

    # === EBOOT 2차 오프셋 테이블 갱신 (크기변경 시 필수! 안 하면 블루스크린) ===
    # 1차 테이블 끝 이후 0패딩 뒤에 오름차순 파일오프셋(2048정렬) 20여개가 있다.
    # 파일 중간을 가리키며, 크기가 바뀌면 이 값들도 새 위치로 옮겨야 한다.
    import bisect
    end1 = PTR + len(ptrs) * 4
    p2 = end1
    while struct.unpack_from("<I", eboot, p2)[0] == 0:
        p2 += 4
    n2 = 0
    prev = -1
    q = p2
    while True:
        v = struct.unpack_from("<I", eboot, q)[0]
        if v == 0 or v < prev or v > dat_size * 1.05:
            break
        prev = v
        q += 4
        n2 += 1
        if n2 > 200:
            break
    updated = 0
    for k in range(n2):
        off = p2 + k * 4
        v = struct.unpack_from("<I", eboot, off)[0]
        j = bisect.bisect_right(ptrs, v) - 1   # v 가 속한 원본 슬롯
        if j < 0:
            continue
        new_v = new_ptrs[j] + (v - ptrs[j])    # 슬롯 시작을 새 위치로, 상대오프셋 유지
        struct.pack_into("<I", eboot, off, new_v)
        updated += 1
    print(f"EBOOT 2차 테이블 갱신 완료: {updated}개 @0x{p2:X}")

    Path(args.out_eboot).write_bytes(eboot)
    print(f"-> {args.out_eboot}")

    print("\n=== 다음 ===")
    print(f"1. {args.out_dat} 를 PSP_GAME/USRDIR/DAT.BIN 자리에")
    print(f"2. {args.out_eboot} 를 EBOOT 자리에 (복호화 EBOOT - PPSSPP는 대체로 실행됨)")
    print("3. PPSSPP로 실행 -> 첫 대사창에서 한글 확인")

if __name__ == "__main__":
    main()