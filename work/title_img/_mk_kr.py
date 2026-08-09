# -*- coding: utf-8 -*-
# 타이틀 카드 한글 이미지 생성 (정선아리랑혼체, 좌측정렬, 첫 글자 확대, 크림 외곽선)
# 레이아웃은 원본 실측 기준: 본문 잉크 하단 y=58 / 부제 잉크높이 26·하단 y=88·우여백 15
# ★x=160 경계는 원본도 글자가 가로지름(창A/창B가 화면에서 맞붙음) = 회피 불필요
# 사용: py work/title_img/_mk_kr.py [슬롯...]   (인자 없으면 전체)
import os, sys, json
os.chdir(r"D:\clean_project")
from PIL import Image, ImageDraw, ImageFont, ImageFilter

F = r"D:\clean_project\work\title_img\정선아리랑혼체TTF.ttf"
W, H = 320, 96
BIG = 1.16          # 첫 글자 확대율 (원본 실측 9~20%)
EDGE = 5            # MaxFilter 커널 = 외곽선 2px
MAIN_BOT = 58       # 본문 잉크 하단 (전 카드 공통)
SUB_H, SUB_BOT, SUB_RM = 26, 88, 15

PAL = json.load(open("work/title_img/_palette.json", encoding="utf-8"))
# slot: (본문, 부제, 본문 잉크높이, 본문 좌여백)  ← 뒤 2개는 원본 실측
CARD = {
    4227: ("하얀 봉우리의 마을", "술즈",          47, 26),
    4298: ("굴뚝의 마을",       "페트나잔카",     48,  8),
    4332: ("수상 도시",         "사니타운",       53, 20),
    4382: ("오아시스 마을",     "아니카말",       51, 15),
    4432: ("하늘을 마주한 마을", "바빌로그라드",   53, 17),
    4462: ("교역 마을",         "벨사스",         46, 19),
    4534: ("풍아궁",            "쿄겐",           44, 23),
    4584: ("메마른 바람의 마을", "라질다",         51, 10),
    4605: ("남해의 문",         "바빌로그라드항", 53, 10),
    4618: ("왕도의 외문",       "발카항",         46, 13),
    4629: ("안개 짙은 왕도",    "발카",           51, 17),
    4700: ("암벽 마을",         "피피스타",       45, 17),
    5018: ("허무의 거리",       "그륀헬데",       54, 11),
    5028: ("매혹의 숨겨진 마을", "우사닌 마을",    50, 12),
}
probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

# 글자 수가 적어 여백이 남는 카드: (본문 높이 배율, 자간 px)
ADJ = {4534: (1.16, 8), 4700: (1.14, 5)}
# 압축 예산 초과 카드: AA 단계 수를 줄여 팔레트 인덱스 종류를 축소 -> 압축률 확보
#   (실측 4227: 6단계 3691B > 예산 3300 / 3단계 3275 / 2단계 2986)
AA = {4227: 2, 4382: 3, 4432: 3}


def draw_run(size, text, first_big, track=0):
    """텍스트를 큰 캔버스에 그려 마스크와 잉크 bbox 반환"""
    f = ImageFont.truetype(F, size)
    fb = ImageFont.truetype(F, int(round(size * BIG))) if first_big else f
    im = Image.new("L", (900, 300), 0)
    d = ImageDraw.Draw(im)
    cx = 100.0
    for i, c in enumerate(text):
        ff = fb if (first_big and i == 0) else f
        w = probe.textlength(c, font=ff)
        if c == " ":
            cx += w * 0.55 + track
            continue
        d.text((cx, 200), c, font=ff, fill=255, anchor="ls")
        cx += w + track
    return im, im.getbbox()


def fit(text, target_h, max_w, first_big, track=0, lo=12, hi=110):
    best = None
    for s in range(lo, hi):
        im, bb = draw_run(s, text, first_big, track)
        if bb is None:
            continue
        h, w = bb[3] - bb[1], bb[2] - bb[0]
        if h > target_h or w > max_w:
            break
        best = (s, im, bb)
    if best is None:
        best = (lo,) + draw_run(lo, text, first_big, track)
    return best


def make(slot):
    main, sub, mh, lx = CARD[slot]
    fill, edge = [tuple(c) for c in PAL[str(slot)]]
    hs, track = ADJ.get(slot, (1.0, 0))
    mh = int(round(mh * hs))

    ms, mim, mbb = fit(main, mh, W - lx - 10, True, track)
    ss, sim, sbb = fit(sub, SUB_H, W - 30, False)

    mask = Image.new("L", (W, H), 0)
    mask.paste(mim.crop(mbb), (lx, MAIN_BOT - (mbb[3] - mbb[1])))
    sw = sbb[2] - sbb[0]
    mask.paste(sim.crop(sbb), (W - SUB_RM - sw, SUB_BOT - (sbb[3] - sbb[1])), sim.crop(sbb))

    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.paste(edge, (0, 0), mask.filter(ImageFilter.MaxFilter(EDGE)))
    im.paste(fill, (0, 0), mask)
    if slot in AA:
        step = 255 // (AA[slot] - 1)
        a = im.getchannel("A").point(lambda v: int(round(v / step)) * step)
        im.putalpha(a)
    im.save("work/title_img/kr_%d.png" % slot)
    return ms, mbb[2] - mbb[0], ss, sw


if __name__ == "__main__":
    slots = [int(a) for a in sys.argv[1:]] or sorted(CARD)
    for slot in slots:
        ms, mw, ss, sw = make(slot)
        print("slot %-5d main %2dpt w=%3d (1st %2dpt) | sub %2dpt w=%3d"
              % (slot, ms, mw, int(round(ms * BIG)), ss, sw))
