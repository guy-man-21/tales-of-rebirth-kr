# -*- coding: utf-8 -*-
# 마을 타이틀 카드 14개 일괄 주입 (kr_<슬롯>.png -> DAT_jp_final.BIN)
#   py work/title_img/_inject_all.py            # 드라이런(압축 예산만 확인)
#   py work/title_img/_inject_all.py --apply    # 실제 주입
#   py work/title_img/_inject_all.py --apply 4227   # 특정 슬롯만
# ★_patch_title.py 의 3규칙(스트림 뒤 원본복원 / 변경픽셀만 / 창 틈 보존)을 그대로 따른다.
import os, sys, bisect, struct, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _patch_title as T                      # ★ import 시 프로젝트 루트로 chdir
from PIL import Image
from pythonlib.utils import comptolib

IMG_OFF, PAL_OFF, WIDTH = 0x60, 0x3C70, 160   # 전 14개 공통 (헤더 실측)
ENTRY = {4227: (0x13554B9C, 3288), 4298: (0x151933B0, 4450), 4332: (0x15D3E340, 3820),
         4382: (0x16FC6854, 3852), 4432: (0x180D16B8, 4430), 4462: (0x18C2556C, 3733),
         4534: (0x1A2D3A7C, 3513), 4584: (0x1B78CD88, 4645), 4605: (0x1C0666F8, 4559),
         4618: (0x1C4248C8, 4135), 4629: (0x1C705CD8, 4485), 4700: (0x1DDDCECC, 3752),
         5018: (0x24DAE1C4, 4053), 5028: (0x24EE3628, 5455)}


def build(slot, off, csz, dat0):
    d = bytearray(comptolib.decompress_data(dat0[off:off + 9 + csz]))
    pal = T.read_pal(d, PAL_OFF)
    H = (PAL_OFF - IMG_OFF) * 2 // WIDTH

    orig = Image.new("RGBA", (WIDTH, H))
    op = orig.load()
    for y in range(H):
        for x in range(WIDTH):
            b = d[IMG_OFF + (y * WIDTH + x) // 2]
            op[x, y] = pal[(b & 0xF) if x % 2 == 0 else (b >> 4)]

    kr = Image.open("work/title_img/kr_%d.png" % slot).convert("RGBA")
    im = T.from_windows_layout(kr, WIDTH, H, orig)     # 원본 위에 두 창만 덮어씀
    px = im.load()

    changed = 0
    for y in range(H):
        for x in range(WIDTH):
            if px[x, y] == op[x, y]:
                continue
            changed += 1
            r, g, b, al = px[x, y]
            if al < 8:
                v = 0
            else:
                v = min(((r - p[0]) ** 2 + (g - p[1]) ** 2 + (b - p[2]) ** 2 + ((al - p[3]) ** 2) * 2, i)
                        for i, p in enumerate(pal) if i)[1]
            bi = IMG_OFF + (y * WIDTH + x) // 2
            d[bi] = (d[bi] & 0xF0) | v if x % 2 == 0 else (d[bi] & 0x0F) | (v << 4)
    return d, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("slots", nargs="*", type=int)
    a = ap.parse_args()
    slots = a.slots or sorted(ENTRY)

    dat0 = open("DAT.BIN", "rb").read()
    ptrs0 = T.read_ptrs("ULJS00132_EBOOT.BIN", len(dat0))
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    ptrs1 = T.read_ptrs("EBOOT_jp_new.BIN", len(dat))

    ok = fail = 0
    for slot in slots:
        off, csz = ENTRY[slot]
        d, changed = build(slot, off, csz, dat0)
        comp = comptolib.compress_data(bytes(d), version=dat0[off])
        pad = 0
        while dat0[off + 9 + csz + pad] in (0x23, 0x00) and pad < 8:
            pad += 1
        budget = 9 + csz + pad
        st = "OK " if len(comp) <= budget else "초과"
        if len(comp) > budget:
            fail += 1
        else:
            ok += 1
        print("slot %-5d %s 압축 %5d / 예산 %5d (%+5d)  변경 %5dpx"
              % (slot, st, len(comp), budget, budget - len(comp), changed))
        if not a.apply or len(comp) > budget:
            continue
        si = bisect.bisect_right(ptrs0, off) - 1
        toff = ptrs1[si] + (off - ptrs0[si])
        if dat[toff] != dat0[off]:
            print("  [!] 대상 @0x%X 타입 불일치 - 스킵" % toff)
            fail += 1
            ok -= 1
            continue
        dat[toff:toff + len(comp)] = comp
        dat[toff + len(comp):toff + budget] = dat0[off + len(comp):off + budget]  # 뒤는 원본 복원

    if a.apply:
        open("DAT_jp_final.BIN", "wb").write(bytes(dat))
        print("[OK] DAT_jp_final.BIN 기록 (크기불변 %dB)" % len(dat))
    print("적합 %d / 초과 %d" % (ok, fail))


if __name__ == "__main__":
    main()
