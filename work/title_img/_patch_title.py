#!/usr/bin/env python3
# 마을 타이틀(anp3) 추출/주입 도구.
#  구조: DAT 내 번들 슬롯 -> comptolib 엔트리 'anp3' -> [헤더][4bpp 이미지][팔레트 16색(알파 0~0x80)]
#  술즈: anp3 @0x13554B9C (csz 3288, dsz 15600), 이미지 +0x60, 160x192(80B/행), 팔레트 +0x3C70.
#  ★과거 "좌우 2벌"은 폭 320 오판이 만든 접힘 아티팩트. 실제 160x192 = 위/아래 절반(각 160x96)이
#    게임이 샘플링하는 두 조각(GE 정점: uv 0..158 x 0..95, 화면 x21-141 / x141-261 로 인접 배치).
#    -> --layout line 이 [상단][하단] 을 좌우로 붙여 320x96 편집 캔버스로 뽑고 주입 시 되돌림.
#  주입: PNG -> 팔레트 양자화 -> 4bpp 패킹 -> 재압축 -> footprint 이내면 in-place.
#
#  사용:
#    py work\title_img\_patch_title.py extract --off 0x13554B9C --csz 3288 --img-off 0x60 \
#       --pal-off 0x3C70 --width 320 --out sulz.png
#    py work\title_img\_patch_title.py inject  --off 0x13554B9C --csz 3288 --img-off 0x60 \
#       --pal-off 0x3C70 --width 320 --png sulz_edit.png [--dat DAT_jp_final.BIN] [--budget 3311]
import argparse
import os
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib
from PIL import Image


def read_ptrs(ebpath, dsize):
    eb = open(ebpath, "rb").read()
    PTR = 0x126F90
    p = []
    i = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + i * 4)[0]
        if i > 0 and (v < p[-1] or v > dsize * 1.05):
            break
        p.append(v)
        i += 1
        if i > 40000:
            break
    return p


def load_entry(datpath, off, csz):
    dat = open(datpath, "rb").read()
    d = comptolib.decompress_data(dat[off:off + 9 + csz])
    return bytearray(d)


def unswizzle_clut(raw32):
    # PS2 CSM1: 32엔트리 블록 [0..7][16..23][8..15][24..31] -> 유효 16색 = [0..7]+[16..23]
    return raw32[0:8] + raw32[16:24]


def read_pal(d, pal_off):
    raw = []
    for i in range(32):
        r, g, b, a = d[pal_off + i * 4:pal_off + i * 4 + 4]
        raw.append((r, g, b, min(255, a * 2)))
    return unswizzle_clut(raw)


# 게임이 샘플링하는 두 창 (파일 이미지 160x192 기준, 마스크 상관 99%+ 로 확정)
#   창A(白峰の)  = (0, 0)   에서 160x96
#   창B(村+부제) = (32, 96) 에서 160x96, 가로 wrap
WINDOWS = [(0, 0), (32, 96)]
WIN_W, WIN_H = 160, 96


def _win_pixels(W, H, ox, oy):
    """창(WIN_W x WIN_H)의 각 픽셀 -> 네이티브 선형 좌표. ★행별 roll 이 아니라
    선형 오프셋(base = oy*W + ox)에서 stride W 로 연속 — 32px 구간이 다음 행으로 넘어간다."""
    base = oy * W + ox
    for wy in range(WIN_H):
        for wx in range(WIN_W):
            lin = base + wy * W + wx
            if lin >= W * H:
                continue
            yield wx, wy, lin % W, lin // W


def to_windows_layout(im):
    """네이티브(160x192) -> 두 창을 화면 순서대로 좌우로 붙인 320x96 편집 캔버스."""
    W, H = im.size
    src = im.load()
    cv = Image.new("RGBA", (WIN_W * len(WINDOWS), WIN_H), (0, 0, 0, 0))
    dst = cv.load()
    for i, (ox, oy) in enumerate(WINDOWS):
        for wx, wy, nx, ny in _win_pixels(W, H, ox, oy):
            dst[i * WIN_W + wx, wy] = src[nx, ny]
    return cv


def from_windows_layout(cv, W, H, orig=None):
    """편집 캔버스 -> 네이티브 역변환 (선형 매핑).
    ★두 창이 덮지 못하는 틈(창A 끝 ~ 창B 시작 사이 32px 등)에 게임이 읽는 데이터가
    있으므로, 빈 캔버스가 아니라 **원본 위에** 창만 덮어써야 한다(실측: 0으로 지우면
    타이틀이 통째로 안 그려짐)."""
    cv = cv.convert("RGBA")
    src = cv.load()
    out = orig.copy() if orig is not None else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dst = out.load()
    for i, (ox, oy) in enumerate(WINDOWS):
        for wx, wy, nx, ny in _win_pixels(W, H, ox, oy):
            dst[nx, ny] = src[i * WIN_W + wx, wy]
    return out


def do_extract(a):
    d = load_entry("DAT.BIN", a.off, a.csz)
    pal = read_pal(d, a.pal_off)
    avail = a.pal_off - a.img_off
    W = a.width
    H = avail * 2 // W
    im = Image.new("RGBA", (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            b = d[a.img_off + (y * W + x) // 2]
            v = (b & 0xF) if x % 2 == 0 else (b >> 4)
            px[x, y] = pal[v]
    if a.layout == "win":
        im = to_windows_layout(im)
    im.save(a.out)
    print(f"[OK] {a.out} {im.size} layout={a.layout} 팔레트16: {pal}")


def do_inject(a):
    d = load_entry("DAT.BIN", a.off, a.csz)   # 원본에서 항상 깨끗하게
    pal = read_pal(d, a.pal_off)
    im = Image.open(a.png).convert("RGBA")
    W = a.width
    avail = a.pal_off - a.img_off
    H = avail * 2 // W
    # 원본 네이티브 이미지 (변경분 비교 + 창 역변환의 바탕)
    orig_im = Image.new("RGBA", (W, H))
    opx = orig_im.load()
    for y in range(H):
        for x in range(W):
            b0 = d[a.img_off + (y * W + x) // 2]
            v0 = (b0 & 0xF) if x % 2 == 0 else (b0 >> 4)
            opx[x, y] = pal[v0]
    if a.layout == "win":
        # ★빈 캔버스가 아니라 원본 위에 창을 덮어써야 틈(32px)의 데이터가 보존된다
        im = from_windows_layout(im, W, H, orig_im)
    if im.size != (W, H):
        print(f"[!] PNG 크기 {im.size} != ({W},{H})")
        return
    # 팔레트 양자화 (최근접, 투명=0) — 원본과 다른 픽셀만
    px = im.load()
    changed = 0
    for y in range(H):
        for x in range(W):
            if px[x, y] == opx[x, y]:
                continue
            changed += 1
            r, g, b, al = px[x, y]
            if al < 8:
                v = 0
            else:
                best = None
                for i, (pr, pg, pb, pa) in enumerate(pal):
                    if i == 0:
                        continue
                    err = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2 + ((al - pa) ** 2) * 2
                    if best is None or err < best[0]:
                        best = (err, i)
                v = best[1]
            byte_i = a.img_off + (y * W + x) // 2
            if x % 2 == 0:
                d[byte_i] = (d[byte_i] & 0xF0) | v
            else:
                d[byte_i] = (d[byte_i] & 0x0F) | (v << 4)
    print(f"[변경분] {changed}px 만 기록")
    # 재압축
    dat0 = open("DAT.BIN", "rb").read()
    t = dat0[a.off]
    comp = comptolib.compress_data(bytes(d), version=t)
    budget = a.budget if a.budget else (9 + a.csz)
    # ★압축 스트림이 원본보다 크게 짧으면 게임이 리소스를 건너뛴다(실측:
    #   원본 3288 OK / 3217 OK / 2855 실패). 화면에 안 보이는 저알파 인덱스
    #   (알파테스트 >=0x80 에서 탈락)를 투명영역에 뿌려 크기만 맞춘다.
    # 크기보정은 기본 OFF (실측: 크기는 변수가 아님. 3198 KR 실패 / 3217 JP 성공)
    target = a.min_csize
    if len(comp) < target:
        H2 = (a.pal_off - a.img_off) * 2 // W
        base = bytearray(d)
        # 투명 픽셀 후보를 흩어진 순서로 수집
        cands = []
        for y in range(H2):
            for x in range(W):
                bi = a.img_off + (y * W + x) // 2
                cur = (base[bi] & 0xF) if x % 2 == 0 else (base[bi] >> 4)
                if cur == 0:
                    cands.append((x, y, bi))
        cands.sort(key=lambda p: ((p[0] * 7 + p[1] * 13) % 9973, p[1], p[0]))

        def build(k):
            dd = bytearray(base)
            for i in range(k):
                x, y, bi = cands[i]
                v = 1 + ((x * 7 + y * 13) & 3)     # 인덱스 1~4 = 알파 12~90 (알파테스트 탈락 = 비표시)
                if x % 2 == 0:
                    dd[bi] = (dd[bi] & 0xF0) | v
                else:
                    dd[bi] = (dd[bi] & 0x0F) | (v << 4)
            return dd

        lo_k, hi_k = 0, len(cands)
        best = None
        for _ in range(16):
            mid = (lo_k + hi_k) // 2
            dd = build(mid)
            c2 = comptolib.compress_data(bytes(dd), version=t)
            if len(c2) >= target:
                if len(c2) <= budget and (best is None or len(c2) < best[0]):
                    best = (len(c2), mid, dd, c2)
                hi_k = mid
            else:
                lo_k = mid + 1
            if hi_k <= lo_k:
                break
        if best:
            _, k, d, comp = best
            print(f"[크기보정] 저알파 노이즈 {k}px -> 압축 {len(comp)}B (목표 {target}, 예산 {budget})")
        else:
            print(f"[크기보정 실패] 목표 {target}B 도달 불가 — 수동 조정 필요")
    print(f"재압축 {len(comp)}B / 예산 {budget}B -> {'OK' if len(comp) <= budget else '초과!'}")
    if len(comp) > budget:
        print("[!] 압축 초과 — 이미지 단순화(색 수/디테일 축소) 필요")
        return
    # ★대상 DAT 는 폰트 repack 등으로 오프셋이 시프트됨 -> 슬롯 상대오프셋으로 재계산
    import bisect
    ptrs0 = read_ptrs("ULJS00132_EBOOT.BIN", len(dat0))
    slot = bisect.bisect_right(ptrs0, a.off) - 1
    rel = a.off - ptrs0[slot]
    target = a.dat
    dat = bytearray(open(target, "rb").read())
    ptrs1 = read_ptrs(a.eboot, len(dat))
    toff = ptrs1[slot] + rel
    # 안전검증: 대상 위치의 원본 압축헤더가 소스와 동일해야 함(첫 주입 시) 또는 이미 주입된 상태
    if dat[toff] != t:
        print(f"[!] 대상 @0x{toff:X} 타입 불일치 ({dat[toff]} != {t}) — 오프셋 재확인 필요")
        return
    print(f"슬롯 {slot} 상대 +0x{rel:X} -> 대상 오프셋 0x{toff:X}")
    dat[toff:toff + len(comp)] = comp
    # ★스트림 뒤는 널로 덮으면 안 됨 — 엔트리 디스크립터(예: 00000001 0000000c ...)가 있어
    #   덮으면 게임이 스프라이트를 그리지 않는다(실측). 원본 바이트를 그대로 복원한다.
    tail = dat0[a.off + len(comp):a.off + budget]
    dat[toff + len(comp):toff + budget] = tail
    open(target, "wb").write(bytes(dat))
    print(f"[OK] {target} @0x{toff:X} anp3 주입 (크기불변 {len(dat)}B)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["extract", "inject"])
    ap.add_argument("--off", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--csz", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--img-off", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--pal-off", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--width", type=int, default=160)
    ap.add_argument("--out", default="work/title_img/extracted.png")
    ap.add_argument("--png", default=None)
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    ap.add_argument("--budget", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--eboot", default="EBOOT_jp_new.BIN")
    ap.add_argument("--min-csize", type=lambda s: int(s, 0), default=0,
                    help="압축 스트림 최소 크기(미달 시 저알파 노이즈로 보정). 기본=원본*0.97")
    ap.add_argument("--layout", choices=["native", "win"], default="win",
                    help="win: 게임이 그리는 두 창을 좌우로 붙인 320x96 캔버스로 편집(무손실)")
    a = ap.parse_args()
    if a.mode == "extract":
        do_extract(a)
    else:
        if not a.png:
            print("--png 필요")
            return
        do_inject(a)


if __name__ == "__main__":
    main()
