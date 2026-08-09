#!/usr/bin/env python3
# ============================================================
#  scpk_patch.py -- SCPK 컨테이너에 새 THEIRSCE를 정확히 끼워넣기
#
#  === 컨테이너 구조 (실측 확인) ===
#    [SCPK(4)][version u16][flags u16][file_amount u32][padding u32]
#    [크기테이블 u32 x file_amount]
#    [블롭0][블롭1]...            <- 각 블롭은 4바이트 정렬(패딩문자 '#')
#
#  각 블롭 = comptolib 헤더 9B + 데이터
#    헤더 = type(1B) + csize(u32) + dsize(u32)
#    CN판의 THEIRSCE 블롭은 type=0(무압축)이라 csize == dsize == 데이터길이.
#    크기테이블 값 S = align4(9 + 데이터길이).   (5개 씬에서 검증)
#
#  flags=0xF 이면 MAP|CHR|SCE|UNK -> THEIRSCE(SCE) 뒤에 UNK 블롭(4B)이 더 있다.
#
#  === 왜 이 모듈이 필요한가 ===
#  기존 fix_container 는 컨테이너를 파싱하지 않고 "파일 앞부분 uint32 를 훑어
#  영역크기와 비슷한 값"을 크기테이블 항목으로 추측했다. 그래서
#    - 꼬리 길이가 씬마다 달라(11~1600B) 96개 씬에서 항목을 못 찾았고
#    - THEIRSCE 앞 9바이트 comptolib 헤더를 갱신하지 않아 크기 정보가 낡은 채 남았다.
#  또, EBOOT 포인터가 컨테이너 시작을 정확히 가리키지 않는다(씬마다 0~-60B 어긋남).
#  따라서 SCPK 매직을 DAT 에서 역방향으로 찾아 헤더를 정식 파싱해야 한다.
#
#  === 크기 제약 ===
#  없다. repack_psp_dat.py 가 DAT 를 재조립하며 EBOOT 포인터를 다시 계산하므로
#  슬롯 크기가 변해도 된다. 컨테이너 내부는 크기테이블만 맞으면 된다.
#  (기존 파이프라인의 "번역을 줄여야 함" 제약은 이 구조를 몰라서 생긴 것)
# ============================================================
import struct

MAGIC = b"SCPK"
HDR_LEN = 9          # comptolib: type(1) + csize(4) + dsize(4)
COMP_RAW = 0         # 무압축
PAD_CHAR = b"#"      # SCPK 가 블롭 정렬에 쓰는 패딩문자


def _align4(n):
    return (n + 3) & ~3


def find_container(dat, ptrs, scene, back=256):
    """DAT 에서 씬의 SCPK 컨테이너를 찾아 구조를 해석한다.
    반환: dict(base, flags, sizes, blob_index, blob_start, blob_size, theirsce_off)"""
    p0, p1 = ptrs[scene], ptrs[scene + 1]
    base = dat.rfind(MAGIC, max(0, p0 - back), p0 + 8)
    if base < 0:
        raise ValueError(f"SCPK 매직 못 찾음 (슬롯 0x{p0:X} 앞 {back}B 내)")

    version, flags = struct.unpack_from("<HH", dat, base + 4)
    n, pad = struct.unpack_from("<II", dat, base + 8)
    if version != 1 or pad != 0 or not (0 < n < 256):
        raise ValueError(f"SCPK 헤더 이상: ver={version} files={n} pad={pad}")

    sizes = [struct.unpack_from("<I", dat, base + 16 + 4 * k)[0] for k in range(n)]
    data_start = base + 16 + 4 * n

    t = dat.find(b"THEIRSCE", base, p1)
    if t < 0:
        raise ValueError("THEIRSCE 매직 없음")

    cur = data_start
    for k, s in enumerate(sizes):
        if cur <= t < cur + s:
            if t - cur != HDR_LEN:
                raise ValueError(
                    f"THEIRSCE 가 블롭 시작+{t - cur}B (기대 +{HDR_LEN})")
            return {
                "base": base, "flags": flags, "sizes": sizes,
                "blob_index": k, "blob_start": cur, "blob_size": s,
                "theirsce_off": t,
                "table_off": base + 16 + 4 * k,
            }
        cur += s
    raise ValueError("THEIRSCE 를 담은 블롭을 크기테이블에서 못 찾음")


def build_slot(dat, ptrs, scene, new_theirsce):
    """새 THEIRSCE 를 넣은 슬롯 바이트를 만든다.

    새 THEIRSCE 가 원본 블롭 자리(S)에 들어가면 -> 블롭 크기를 S 로 유지하고
    남는 자리는 원본과 같은 '#' 패딩으로 채운다. 크기테이블을 건드릴 필요가 없고
    슬롯 크기도 그대로다 (원본이 이미 그런 정렬 패딩 구조다).

    안 들어가면 -> 블롭을 키우고 크기테이블 항목을 갱신해야 한다.
    이때 테이블 항목이 슬롯 밖(이전 슬롯 영역)에 있을 수 있어 호출자가 처리하도록
    (절대오프셋, 새값) 을 함께 돌려준다.

    반환: (새 슬롯 bytes, table_patch or None, 정보 문자열)
      table_patch = (절대오프셋, u32 새 블롭크기) - 슬롯 안이면 이미 적용돼 있음
    """
    p0, p1 = ptrs[scene], ptrs[scene + 1]
    c = find_container(dat, ptrs, scene)

    L = len(new_theirsce)
    head = bytes([COMP_RAW]) + struct.pack("<II", L, L)
    S = c["blob_size"]
    need = HDR_LEN + L

    if need <= S:
        blob = head + new_theirsce + PAD_CHAR * (S - need)
        new_size = S
        grew = False
    else:
        blob = head + new_theirsce
        blob += PAD_CHAR * (_align4(len(blob)) - len(blob))
        new_size = len(blob)
        grew = True

    bs = c["blob_start"] - p0
    be = bs + S
    if bs < 0:
        raise ValueError("THEIRSCE 블롭이 슬롯 밖에서 시작")

    slot = bytearray(dat[p0:p1])
    patch = None
    if grew:
        off = c["table_off"]
        if p0 <= off < p1:
            struct.pack_into("<I", slot, off - p0, new_size)
        else:
            patch = (off, new_size)   # 이전 슬롯에 걸침 -> 호출자가 처리

    out = bytes(slot[:bs]) + blob + bytes(slot[be:])
    delta = len(out) - (p1 - p0)
    info = (f"블롭[{c['blob_index']}] {S}->{new_size}B"
            + (f", 슬롯 {delta:+d}B" if delta else ", 슬롯 크기 유지")
            + (" [테이블 이전슬롯]" if patch else ""))
    return out, patch, info
