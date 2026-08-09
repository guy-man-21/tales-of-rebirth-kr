#!/usr/bin/env python3
# ============================================================
#  Tales of Rebirth PSP - 폰트(#00014)에 한글 글리프 삽입
#
#  24x24 4bpp 글리프로 한글을 렌더해서 지정한 글리프 슬롯에 써넣고,
#  게임이 받아들이는 비압축(타입0) 폰트로 출력.
#
#  === 사전 준비: JP 폰트 압축 해제 ===
#  JP #00014는 압축(타입1)이라 먼저 풀어야 함. PythonLib에서:
#    import pythonlib.utils.comptolib as c
#    raw = c.decompress_data(open('00014_JP.bin','rb').read(), version=1)
#    open('00014_JP_decomp.bin','wb').write(raw)
#  (또는 CN 폰트 00014_CN.bin 을 base 로 써도 됨 - 이미 비압축)
#
#  === 사용법 ===
#    py font_insert_hangul.py --font 00014_JP_decomp.bin --table 00015_JP.bin \
#         --text "안녕하세요한글" --start 512 --out 00014_patched.bin
#
#  --start : 한글을 넣기 시작할 글리프 인덱스 (기본 512 = 한자 영역 시작 부근)
# ============================================================
import struct, argparse
from pathlib import Path

GLYPH_W = GLYPH_H = 24
GLYPH_BYTES = GLYPH_W * GLYPH_H // 2   # 288

FONT_CANDIDATES = [
    # Noto Sans KR 우선 (Windows에 설치했거나 폴더에 둔 경우)
    "NotoSansKR-Bold.otf",
    "NotoSansKR-Bold.ttf",
    "NotoSansKR-Medium.otf",
    "C:/Windows/Fonts/NotoSansKR-Bold.otf",
    "C:/Windows/Fonts/NotoSansKR-Regular.otf",
    "C:/Windows/Fonts/NotoSansCJKkr-Bold.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",   # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    # 폴백: 맑은 고딕
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/NanumGothicBold.ttf",
]

def find_font():
    from pathlib import Path as P
    for f in FONT_CANDIDATES:
        if P(f).exists():
            return f
    return None

def render_hangul_glyph(ch, font_path, bold_level=1, outline=0, outline_width=1,
                        glow=0, glow_width=3, supersample=1, edge_soft=0.0):
    """한글 1자를 24x24 4bpp(니블값 0~15)로 렌더.
    bold_level: 굵기 팽창. outline: 외곽선 밝기값(0=없음). outline_width: 테두리 두께(px)
    glow: 검은 소프트 후광 최대 밝기(어두운값, 0=없음). glow_width: 후광 두께(px).
          outline 대신 여러 겹의 어두운 링을 안쪽 진하게~바깥 옅게 깔아 번짐 효과.
    supersample: N배 크게 렌더 후 축소(LANCZOS)해 매끈한 안티에일리어싱(원본 폰트 스타일).
                 1=끄기(기존), 3~4=권장."""
    from PIL import Image, ImageFont, ImageDraw, ImageFilter
    ss = max(1, int(supersample))
    BW, BH = GLYPH_W * ss, GLYPH_H * ss
    img = Image.new("L", (BW, BH), 0)
    d = ImageDraw.Draw(img)
    # 외곽선/후광 넣으면 글자를 작게 (테두리 공간 확보). margin 은 24px 기준.
    if glow:
        margin = (1 if bold_level >= 1 else 0) + (glow_width + 1)
    else:
        margin = (1 if bold_level >= 1 else 0) + (outline_width + 1 if outline else 0)
    for fs in range(24 * ss, 15 * ss, -1):
        font = ImageFont.truetype(font_path, fs)
        bbox = d.textbbox((0,0), ch, font=font)
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if w <= BW-margin*ss and h <= BH-margin*ss:
            break
    x = -bbox[0] + max(0,(BW-w)//2)
    y = -bbox[1] + max(0,(BH-h)//2)
    d.text((x,y), ch, font=font, fill=255)
    if ss > 1:
        img = img.resize((GLYPH_W, GLYPH_H), Image.LANCZOS)  # 매끈한 AA
    if edge_soft and edge_soft > 0:
        # 엣지를 넓게 번지게 해 원본 가나처럼 부드러운 그라데이션(테두리 아님)
        img = img.filter(ImageFilter.GaussianBlur(edge_soft))
    import numpy as np
    a = np.array(img).astype(np.int32)
    for _ in range(bold_level):
        dil = np.array(img.filter(ImageFilter.MaxFilter(3))).astype(np.int32)
        a = np.maximum(a, (dil * 0.85).astype(np.int32))
        img = Image.fromarray(a.clip(0,255).astype(np.uint8))
    q = (a * 15 // 255).clip(0,15).astype(np.uint8)

    if glow:
        # 검은 소프트 후광: 코어 마스크를 한 겹씩 팽창시키며 링을 쌓되,
        # 안쪽 링일수록 진하게(glow), 바깥일수록 옅게(->0) 밝기값을 낮춰 번짐 표현.
        mimg = Image.fromarray((q > 2).astype(np.uint8) * 255)
        prev = np.array(mimg) > 0
        for i in range(glow_width):
            mimg = mimg.filter(ImageFilter.MaxFilter(3))
            cur = np.array(mimg) > 0
            ring = cur & (~prev) & (q <= 2)
            val = max(1, int(round(glow * (1.0 - i / float(glow_width)))))
            q[ring] = val
            prev = cur
    elif outline:
        # 글자 마스크를 팽창시켜 외곽 링을 만들고, 그 부분을 낮은 밝기값으로
        mask = (q > 2).astype(np.uint8) * 255
        mimg = Image.fromarray(mask)
        for _ in range(outline_width):  # 테두리 두께(픽셀)
            mimg = mimg.filter(ImageFilter.MaxFilter(3))
        ring = (np.array(mimg) > 0) & (q <= 2)   # 팽창영역 중 글자 아닌 곳
        q[ring] = outline   # 외곽선 밝기값 (예: 3 = 어두움)

    flat = q.flatten()
    out = bytearray()
    for i in range(0, len(flat), 2):
        out.append((flat[i] & 0xF) | ((flat[i+1] & 0xF) << 4))
    return bytes(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="압축 해제된 폰트 (00014_JP_decomp.bin 또는 00014_CN.bin)")
    ap.add_argument("--table", required=True, help="문자코드 테이블 (00015_JP.bin)")
    ap.add_argument("--text", default="안녕하세요한글테스트", help="넣을 한글")
    ap.add_argument("--start", type=int, default=512, help="시작 글리프 인덱스 (연속 삽입)")
    ap.add_argument("--map", default=None,
                    help="특정 슬롯에 삽입: '730:안,1691:녕,3173:하,2125:세,2343:요'")
    ap.add_argument("--header", type=int, default=-46,
                    help="글리프 시작 오프셋(바이트). 이 게임 기본 -46")
    ap.add_argument("--index-offset", type=int, default=-96,
                    help="게임인덱스→파일인덱스 보정. 이 게임 기본 -96 (파일=게임-96)")
    ap.add_argument("--bold-level", type=int, default=1,
                    help="글자 굵기 팽창. 0=원본, 1=약간굵게(기본), 2=굵게")
    ap.add_argument("--outline", type=int, default=0,
                    help="검은 테두리. 0=없음, 6=권장(외곽선 밝기값)")
    ap.add_argument("--outline-width", type=int, default=1,
                    help="테두리 두께(픽셀). 1=얇게, 2=두껍게")
    ap.add_argument("--glow", type=int, default=0,
                    help="검은 소프트 후광 최대 밝기값(0=없음). outline 대신 쓰인다. 강=7 권장")
    ap.add_argument("--glow-width", type=int, default=3,
                    help="후광 두께(픽셀). 강=3")
    ap.add_argument("--supersample", type=int, default=1,
                    help="N배 렌더 후 축소로 매끈한 AA(원본 폰트 스타일). 1=끄기, 4=권장")
    ap.add_argument("--edge-soft", type=float, default=0.0,
                    help="엣지 블러 반경. 테두리 없이 원본 가나처럼 부드러운 그라데이션. 0.6~1.0 권장")
    ap.add_argument("--out", default="00014_patched.bin")
    ap.add_argument("--font-file", default=None, help="한글 TTF 경로 (자동탐색 실패 시)")
    args = ap.parse_args()

    fp = args.font_file or find_font()
    if not fp:
        print("한글 폰트를 못 찾음. --font-file 로 TTF 경로 지정 (예: C:/Windows/Fonts/malgun.ttf)")
        return
    print("사용 폰트:", fp)

    font = bytearray(Path(args.font).read_bytes())
    table = Path(args.table).read_bytes()

    # 게임 기준 인덱스로 입력받아, 파일 위치로 보정
    hdr_len = args.header
    idx_off = args.index_offset
    n_glyphs = (len(font) - max(0,hdr_len)) // GLYPH_BYTES
    print(f"폰트: 헤더 {hdr_len}, 인덱스보정 {idx_off} (게임인덱스 기준 입력)")

    # 문자코드 테이블 (u16 BE)
    codes = [struct.unpack_from(">H", table, i)[0] for i in range(0, len(table)-1, 2)]

    # 삽입 목록 구성: --map 우선, 없으면 --text 연속
    targets = []   # (glyph_index, hangul_char)
    if args.map:
        for pair in args.map.split(","):
            idx_s, ch = pair.split(":")
            targets.append((int(idx_s), ch))
    else:
        for k, ch in enumerate(args.text):
            targets.append((args.start + k, ch))

    print(f"\n=== 한글 삽입 (게임 인덱스 기준) ===")
    for gi, ch in targets:
        file_idx = gi + idx_off          # 게임인덱스 -> 파일인덱스
        off = hdr_len + file_idx * GLYPH_BYTES
        if off < 0 or off + GLYPH_BYTES > len(font):
            print(f"  게임[{gi}] 범위 밖 (바이트 {off})"); continue
        glyph = render_hangul_glyph(ch, fp, args.bold_level, args.outline, args.outline_width,
                                    args.glow, args.glow_width, args.supersample, args.edge_soft)
        font[off:off+GLYPH_BYTES] = glyph
        orig_code = codes[gi] if gi < len(codes) else None
        try:
            orig_ch = struct.pack(">H", orig_code).decode("shift-jis") if orig_code else "?"
        except Exception:
            orig_ch = "?"
        cs = f"{orig_code:04X}" if orig_code is not None else "????"
        print(f"  게임[{gi}](파일{file_idx}) <- '{ch}'   (원래 {cs}='{orig_ch}')")

    # 비압축(타입0) 헤더로 출력
    out_data = bytearray()
    if hdr_len == 0:
        # 9바이트 타입0 헤더 추가
        out_data += bytes(9)   # 00 * 9
        out_data += font
    else:
        font[0] = 0   # 타입0로 강제
        out_data += font
    Path(args.out).write_bytes(out_data)
    print(f"\n출력: {args.out} ({len(out_data)} bytes, 비압축 타입0)")
    print("\n다음: 이 파일을 DAT.BIN의 #00014 자리에 넣고(재패킹), 게임에서")
    print("위에 표시된 '슬롯 코드' 글자가 나오는 텍스트를 띄우면 한글이 보입니다.")

if __name__ == "__main__":
    main()
