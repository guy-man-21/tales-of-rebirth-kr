#!/usr/bin/env python3
# 씬225/226/227 시스템 UI 문자열 = THEIRSCE 내부 '제자리 동일길이' 교체.
#  ★기존 _build.py(THEIRSCE 통째 재구성)는 스크립트 데이터런(좌표/포인터가 한자로 tbl디코드)까지
#    바꿔 배틀종료 크래시(배틀결과 코드가 그 데이터를 float로 읽음). 이 도구는 '의미있는 UI 문장'만
#    바이트 검색해 kr+공백(정확히 jp 바이트길이)으로 덮음 -> 데이터런/오프셋테이블/널구조 100% 불변.
#  디버그 문자열(座標/アニメ/操作説明 등 정상플레이 미출현)은 사전에서 제외.
#  사용: py work\sys225\_inplace.py [--check] [--dat DAT_jp_final.BIN]
import argparse
import json
import os
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tjp = json.load(open("tbl_all.json", encoding="utf-8"))["TBL"]
revjp = {v: k for k, v in Tjp.items()}
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
invkr = {v: int(k, 16) for k, v in Tkr.items()}
PTR = 0x126F90
SCENES = [225, 226, 227]

# 플레이어 대면 UI 문장만 (jp원문 -> kr). 태그는 THEIRSCE opcode라 여기 문자열엔 없음.
DICT = {
    "休憩しますか？": "쉬시겠습니까?",
    "はい": "예",
    "いいえ": "아니오",
    "パーティ編成を保存しました。": "파티 편성을 저장했습니다.",
    "パーティ編成を復元しました。": "파티 편성을 복원했습니다.",
    "パーティ編成しました。": "파티를 편성했습니다.",
    "が仲間になりました。": "가 동료가 됐습니다.",
    "が同行します。": "가 동행합니다.",
    "本来はスクリーンチャットで行われます。": "원래는 스크린챗으로 진행됩니다.",
    "不適切な値を検出しました。": "부적절한 값을 감지했다.",
    "データエラーです。": "데이터 에러입니다.",
    "マップがありません。": "맵이 없습니다.",
    "チェンジマップ時のＢＧ指定を": "체인지맵 시 BG 지정을",
    "確認してください。": "확인해 주세요.",
    "この時系列でフィールドマップに": "이 시간대엔 필드맵으로",
    "出ることはできません。": "나갈 수 없습니다.",
    "誰もいません！": "아무도 없어요!",
    "ガルドを手に入れました。": "갈드를 얻었습니다.",
    "シーラグ橋": "시라그다리",
    "ペトナジャンカ方面とあります。": "페트나쟌카 방면입니다.",
    "入りますか？": "들어갈까요?",
    "サニイタウン方面とありますが": "사니타운 방면입니다만",
    "険しくて登れません……。": "험해서 오를 수 없습니다.",
    "陸地を歩いていると、特定の場所で": "육지를 걷다 보면 특정 장소에서",
    "何かを発見する事があります。": "무언가 발견할 때가 있습니다.",
    "これから、いろいろな場所を歩く事で、": "앞으로 여러 장소를 걸으면서,",
    "様々な種類のものを発見できるでしょう。": "다양한 종류를 발견할 수 있겠죠.",
    "この発見が、どういった意味を持つのか、": "이 발견이 어떤 의미를 지니는지,",
    "それは、後ほどのお楽しみです。": "그건 나중의 즐거움입니다.",
    "宝箱を引き揚げました": "보물상자 건졌습니다",
    "宝箱は見つかりませんでした……": "보물상자를 못 찾았습니다.",
}


# 복합(compound) 메뉴 문자열: 텍스트+제어바이트가 한 null종료 문자열. 통째 교체(태그 보존).
#  <XX>=1B 제어, <XXXX>=2B 코드(전각공백 8140 등). jp/kr 둘 다 같은 태그 구조 유지.
COMPOUND = {
    "休憩しますか？<01><8140>はい<8140><01><8140>いいえ<8140>":
    "쉬시겠습니까?<01><8140>예<8140><01><8140>아니오<8140>",
}

import re as _re
_T4 = _re.compile(r"<([0-9A-Fa-f]{4})>")
_T2 = _re.compile(r"<([0-9A-Fa-f]{2})>")


def _enc_tagged(s, table_rev=None, kr=False):
    o = bytearray()
    i = 0
    while i < len(s):
        m = _T4.match(s, i)
        if m:
            o += struct.pack(">H", int(m.group(1), 16))
            i = m.end()
            continue
        m = _T2.match(s, i)
        if m:
            o.append(int(m.group(1), 16))
            i = m.end()
            continue
        ch = s[i]
        if kr:
            if ch in invkr:
                o += struct.pack(">H", invkr[ch])
            elif ord(ch) < 0x80:
                o.append(ord(ch))
            else:
                return None
        else:
            if ch in revjp:
                o += bytes.fromhex(revjp[ch])
            elif ord(ch) < 0x80:
                o.append(ord(ch))
            else:
                return None
        i += 1
    return bytes(o)


def enc_jp(s):
    o = bytearray()
    for ch in s:
        if ch in revjp:
            o += bytes.fromhex(revjp[ch])
        elif ord(ch) < 0x80:
            o.append(ord(ch))
        else:
            return None
    return bytes(o)


def enc_kr(s):
    o = bytearray()
    for ch in s:
        if ch in invkr:
            o += struct.pack(">H", invkr[ch])
        elif ord(ch) < 0x80:
            o.append(ord(ch))
        else:
            return None
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dat", default="DAT_jp_final.BIN")
    args = ap.parse_args()

    # 사전 인코딩 + 바이트여유 확인
    enc = {}
    over = []
    for jp, kr in DICT.items():
        ej, ek = enc_jp(jp), enc_kr(kr)
        if ej is None:
            print(f"[경고] jp 인코딩불가: {jp!r}")
            continue
        if ek is None:
            print(f"[경고] kr 인코딩불가: {kr!r}")
            continue
        if len(ek) > len(ej):
            over.append((jp, kr, len(ek), len(ej)))
            continue
        enc[jp] = (ej, ek)
    if over:
        print("[초과 - 트림 필요]")
        for jp, kr, a, b in over:
            print(f"  {kr!r} {a}>{b}  (jp {jp!r})")

    dat = bytearray(open(args.dat, "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))

    def is_bound(b):
        # 런 경계: tbl 2B 코드가 아닌(제어<0x81) 바이트면 경계로 인정
        return b < 0x81

    grand = 0
    for SC in SCENES:
        lo, hi = dp[SC], dp[SC + 1]
        t = dat.find(b"THEIRSCE", lo, hi)
        if t < 0:
            print(f"  씬{SC}: THEIRSCE 없음")
            continue
        # display 영역만: THEIRSCE+0x4000 이후 ~ 데이터런('痕狐' 좌표/포인터 zone) 시작 전까지.
        #  ★데이터런 이후는 배틀결과 코드가 float로 읽는 구역이라 절대 금지.
        region_lo = t + 0x4000
        datarun = enc_jp("痕狐")
        dr = dat.find(datarun, t, hi)
        region_hi = dr if dr > 0 else hi
        cnt = 0
        # (0) 복합 메뉴 문자열 통째 교체 (standalone 보다 먼저)
        for jp, kr in COMPOUND.items():
            ej = _enc_tagged(jp)
            ek = _enc_tagged(kr, kr=True)
            if ej is None or ek is None or len(ek) > len(ej):
                if ek and len(ek) > len(ej):
                    print(f"  [복합초과] {kr!r} {len(ek)}>{len(ej)}")
                continue
            start = region_lo
            while True:
                pos = dat.find(ej, start, region_hi)
                if pos < 0:
                    break
                if not args.check:
                    dat[pos:pos + len(ej)] = ek + b" " * (len(ej) - len(ek))
                cnt += 1
                start = pos + len(ej)
        # 긴 문자열 우선(부분매칭 방지)
        for jp in sorted(enc, key=lambda k: -len(enc[k][0])):
            ej, ek = enc[jp]
            start = region_lo
            while True:
                pos = dat.find(ej, start, region_hi)
                if pos < 0:
                    break
                # 경계 검사: 앞 1B, 뒤 1B 가 tbl코드 중간이 아님
                prev_ok = pos == region_lo or is_bound(dat[pos - 1])
                nb = dat[pos + len(ej)]
                next_ok = is_bound(nb)
                if prev_ok and next_ok:
                    if not args.check:
                        dat[pos:pos + len(ej)] = ek + b" " * (len(ej) - len(ek))
                    cnt += 1
                start = pos + len(ej)
        print(f"  씬{SC}: THEIRSCE@{hex(t)} 치환 {cnt}건")
        grand += cnt

    print(f"[{'검사' if args.check else '적용'}] 총 {grand}건 / 사전 {len(enc)}종 (초과 {len(over)})")
    if not args.check and grand and not over:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 씬225/226/227 제자리 (크기·데이터런·널구조 불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
