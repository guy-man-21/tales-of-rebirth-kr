#!/usr/bin/env python3
# 최소 TIM2 디코더/인코더 (ToR PSP용).
#  지원: itype 4(CLUT4)/5(CLUT8)/3(RGBA8888)/2(RGB888)/1(RGBA5551)
#  CLUT8 팔레트는 PS2 CSM1 스위즐(8색 블록 교차) 해제.
import struct

from PIL import Image


def _unswizzle_clut(pal):
    # PS2 CSM1: 32색 단위로 [0..7][16..23][8..15][24..31]
    out = list(pal)
    for base in range(0, len(pal), 32):
        blk = pal[base:base + 32]
        if len(blk) < 32:
            break
        out[base:base + 32] = blk[0:8] + blk[16:24] + blk[8:16] + blk[24:32]
    return out


def _read_pal(d, off, ccol, ctype):
    fmt = ctype & 0x3F
    pal = []
    if fmt == 3:  # RGBA8888(PS2: A 0..0x80)
        for i in range(ccol):
            r, g, b, a = struct.unpack_from("<4B", d, off + i * 4)
            pal.append((r, g, b, min(255, a * 2)))
    elif fmt == 2:  # RGB888
        for i in range(ccol):
            r, g, b = struct.unpack_from("<3B", d, off + i * 3)
            pal.append((r, g, b, 255))
    else:  # 1 = RGBA5551
        for i in range(ccol):
            v = struct.unpack_from("<H", d, off + i * 2)[0]
            r = (v & 31) << 3
            g = ((v >> 5) & 31) << 3
            b = ((v >> 10) & 31) << 3
            a = 255 if (v >> 15) else 0
            pal.append((r, g, b, a))
    return pal


def parse(d, p):
    """d[p:] 가 TIM2 픽처. 반환 dict(헤더 필드 + 데이터 오프셋)."""
    assert d[p:p + 4] == b"TIM2"
    tsz, csz, isz = struct.unpack_from("<III", d, p + 0x10)
    hsz, ccol = struct.unpack_from("<HH", d, p + 0x1C)
    pfmt, mip, ctype, itype = struct.unpack_from("<BBBB", d, p + 0x20)
    w, h = struct.unpack_from("<HH", d, p + 0x24)
    img_off = p + 0x10 + hsz
    clut_off = img_off + isz
    return {"p": p, "total": tsz, "clut_size": csz, "img_size": isz, "hdr_size": hsz,
            "ccol": ccol, "ctype": ctype, "itype": itype, "w": w, "h": h,
            "img_off": img_off, "clut_off": clut_off}


def decode(d, p):
    t = parse(d, p)
    w, h = t["w"], t["h"]
    im = Image.new("RGBA", (w, h))
    px = im.load()
    io_, co = t["img_off"], t["clut_off"]
    it = t["itype"]
    if it == 5:  # CLUT8
        pal = _read_pal(d, co, t["ccol"], t["ctype"])
        if t["ccol"] == 256:
            pal = _unswizzle_clut(pal)
        for y in range(h):
            for x in range(w):
                px[x, y] = pal[d[io_ + y * w + x]]
    elif it == 4:  # CLUT4
        pal = _read_pal(d, co, t["ccol"], t["ctype"])
        for y in range(h):
            for x in range(w):
                b = d[io_ + (y * w + x) // 2]
                v = b & 0xF if (x % 2 == 0) else b >> 4
                px[x, y] = pal[v]
    elif it == 3:  # RGBA8888
        for y in range(h):
            for x in range(w):
                r, g, b, a = struct.unpack_from("<4B", d, io_ + (y * w + x) * 4)
                px[x, y] = (r, g, b, min(255, a * 2))
    elif it == 2:  # RGB888
        for y in range(h):
            for x in range(w):
                r, g, b = struct.unpack_from("<3B", d, io_ + (y * w + x) * 3)
                px[x, y] = (r, g, b, 255)
    elif it == 1:  # RGBA5551
        for y in range(h):
            for x in range(w):
                v = struct.unpack_from("<H", d, io_ + (y * w + x) * 2)[0]
                px[x, y] = ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3,
                            255 if (v >> 15) else 0)
    else:
        raise ValueError(f"itype {it} 미지원")
    return im, t
