#!/usr/bin/env python3
# 슬롯3960 UI구간 잔여 미번역 엔트리 전량 번역 (2026-07-18 전면해결).
#  keyhelp_remain.json(원본과 동일=미패치 엔트리, CN오라클) 기반.
#  엔트리를 태그/텍스트 조각으로 분해 -> PIECE 사전 번역 -> 재조립 -> kr+공백 '정확히 jplen' 채움.
#  CN이 번역한 엔트리만(cn_tr) 대상. 팔레트/디버그 스킵. 초과/미사전 조각은 리포트만.
#  사용: py work\menu_jp\_keyhelp_full.py [--check] [--dat DAT_jp_final.BIN]
import argparse
import json
import os
import re
import struct

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
invkr = {v: int(k, 16) for k, v in Tkr.items()}
PTR = 0x126F90
SLOT = 3960
TAG = re.compile(r"<[0-9A-F]{2}>|<[0-9A-F]{4}>")
T4 = re.compile(r"<([0-9A-F]{4})>")
T2 = re.compile(r"<([0-9A-F]{2})>")

# 스킵: 디버그/이름입력 팔레트(한글 자모 팔레트는 별도 과제)
SKIP_ROFF = {0xF000, 0xF034, 0xF081, 0x111E3}

# 텍스트 조각 사전 (jp -> kr). 인코딩 후 엔트리 총합 <= jplen 검증됨.
PIECE = {
    # 공통 버튼/라벨
    "説明切替": "설명전환", "リスト切替": "목록전환", "変更": "변경",
    "キャラ切替": "캐릭터전환", "操作切替": "조작전환", "削除": "삭제",
    "個数変更": "개수변경", "設定個所切替": "설정항목전환", "元に戻す": "되돌리기",
    "デフォルト": "기본값", "倍率切替": "배율전환", "使う": "사용",
    "捨てる": "버리기", "実行": "실행", "カーソル": "커서",
    "終了する": "종료하기", "入替": "교체", "名称変更": "명칭변경",
    "称号変更": "칭호변경", "画像切替": "화상전환", "作戦切替": "작전전환",
    "作戦名変更": "작전명변경", "選択": "선택", "戻す": "복원", "戻る": "뒤로",
    "停止": "정지", "再生": "재생", "入力": "입력", "リスト": "목록",
    "ソート": "정렬", "下線先表示": "밑줄표시", "下線移動": "밑줄이동",
    "やめる": "그만", "スキップ": "스킵", "繰返し設定": "반복설정",
    "購入": "구입", "売却": "매각", "買う": "구입", "売る": "판매",
    "設定": "설정", "隊列": "대열", "戦術": "전술", "引き継ぐ": "이어받기",
    "装備する": "장착하기", "装備メニュー": "장비메뉴", "装備": "장비",
    "外して装備": "벗겨 장착", "奥義習得": "오의습득", "対戦決定": "대전결정",
    "セーブデータ削除": "세이브 삭제", "アンフォーマット": "언포맷",
    "オートセーブ": "오토세이브", "コメント表示": "코멘트표시",
    "コメント編集": "코멘트편집", "敵リスト": "적 목록", "ライン": "라인",
    "進行中": "진행중", "購入切替": "구입전환", "表示切替": "표시전환",
    "前の画像へ": "이전화상", "先の画像へ": "다음화상", "ヘルプを消す": "헬프 끄기",
    "位置変更": "위치변경", "移動／店リスト": "이동／상점목록",
    "サルベージ": "샐비지", "店リスト": "상점목록", "再生／一時停止": "재생／일시정지",
    "料理する": "요리하기", "料理メニュー終了": "요리메뉴 종료",
    "オート料理設定": "오토요리 설정", "オート料理登録切替": "오토요리 등록전환",
    "オート料理": "오토요리", "おすすめ隊列": "추천 대열",
    # 카테고리 1자
    "薬": "약", "剣": "검", "槍": "창", "杖": "장", "鎧": "갑", "服": "옷", "曲": "곡",
    "街": "촌",
    # 조사/짧은 연결어 (런타임 삽입 앞뒤)
    "の": "의", "は": "는", "が": "가", "を": "를", "に": "에", "に、": "에,",
    "その": "그", "」を": "」를", "名称「": "명칭「", "・": "・", "KB以上": "KB이상",
    # 문장
    "よろしいですか？": "괜찮습니까?",
    "これでいいですか？": "이대로 좋습니까?",
    "でいいですか？": "로 좋습니까?",
    "選択中のデータを削除します。": "선택한 데이터를 삭제합니다.",
    "アンフォーマットしますか？": "언포맷합니까?",
    "データは全て消えてしまいますので": "데이터가 전부 사라지므로",
    "キャンセル時は慎重に": "취소 시엔 신중하게",
    "を押してください": "를 눌러 주세요",
    "選択中のデータ以降に連続でセーブしていきます。": "선택한 데이터 이후로 연속 저장합니다.",
    "押しっぱなしでセーブを途中終了できます。": "계속 누르면 저장을 도중 종료합니다.",
    "削除中です。": "삭제 중.",
    "アンフォーマット中です。": "언포맷 중입니다.",
    "連続セーブ中です。": "연속 저장 중.",
    "を抜いたり": "를 뽑거나",
    "電源を切ったりしないでください": "전원을 끄거나 하지 마세요",
    "メニューを終了しますか？": "메뉴를 종료합니까?",
    "セーブを終了しますか？": "저장을 종료합니까?",
    "貸し出し中の本": "대출 중인 책",
    "今は一冊も借りていない。": "지금은 한 권도 안 빌렸다.",
    "装備中ですが捨てますか？": "장착 중인데 버립니까?",
    "装備中です。": "장착 중입니다.",
    "装備中の武器は捨てられません。": "장착 중인 무기는 못 버립니다.",
    "装備を変えますか？": "장비를 바꿉니까?",
    "装備中ですがどうしますか？": "장착 중인데 어떡할까요?",
    "作戦名にあわせたおすすめ設定を行います。": "작전명에 맞는 추천 설정을 합니다.",
    "継承しますか？": "계승합니까?",
    "は失われます）": "는사라집니다）",
    "引き継ぎますか？": "이어받습니까?",
    "作成できます。": "작성 가능합니다.",
    "合成しますか？": "합성합니까?",
    "装備しますか？": "장착합니까?",
    "フィールド上での": "필드에서의",
    "シャオルーンに乗っているときの": "샤오룬 탑승 중의",
    "[ターゲット]": "[타겟]",
    "プレイヤーのターゲットを画面内に表示します。": "플레이어의 타겟을 화면 내에 표시합니다.",
    "[パーティ]": "[파티]",
    "パーティキャラを画面内に表示します。": "파티 캐릭터를 화면 내에 표시합니다.",
    "[エネミー]": "[적]",
    "敵全員を画面内に表示します。": "적 전원을 화면 내에 표시합니다.",
    "[オール]": "[전체]",
    "キャラクター全員を画面内に表示します。": "캐릭터 전원을 화면 내에 표시합니다.",
    "全ての変更を破棄して": "모든 변경을 파기하고",
    "元に戻しますか？": "되돌립니까?",
    "全てをデフォルトに戻しますか？": "전부 기본값으로 되돌립니까?",
    "入力を取りやめますか？": "입력을 취소합니까?",
    "（入力の反映は文字リスト上で": "（입력 반영은 문자목록에서",
    "は現在設定されていません。": "는 현재 미설정입니다.",
    "設定項目は料理リスト上で": "설정항목은 요리목록에서",
    "を料理しますか？": "를 요리합니까?",
    "%追加": "%추가",
    "シークレットファクター「": "시크릿팩터「",
    "シークレットファクター": "시크릿팩터",
    "HP回復": "HP회복", "HPが": "HP가", "RGが": "RG가",
    "特殊効果「": "특수효과「",
    "発生。": "발생.",
    "を中止しますか？": "를 중지합니까?",
    "空き容量が足りません。": "빈 용량이 부족합니다.",
    "新規作成には": "신규작성에는",
    "このゲームのデータを新規作成する為の": "이 게임 데이터 신규작성을 위한",
    "このゲームの中断データを新規作成する為の": "이 게임 중단데이터 신규작성을 위한",
    "選択中のデータに上書きセーブします。": "선택한 데이터에 덮어씁니다.",
    "データを新規作成します。よろしいですか？": "데이터를 신규작성합니다. 괜찮습니까?",
    "フォーマットされていません。フォーマットしますか？": "포맷되지 않았습니다. 포맷합니까?",
    "選択中のデータをロードします。よろしいですか？": "선택한 데이터를 로드합니다. 괜찮습니까?",
    "変更されたコメントを": "변경된 코멘트를",
    "ゲームを中断しますか？": "게임을 중단합니까?",
    "ただし、再開後は中断データが": "단, 재개 후엔 중단 데이터가",
    "なくなりますのでご注意ください": "사라지므로 주의해 주세요",
    "（中断データは上書きされます）": "（중단데이터는 덮어써집니다）",
    "中です。": "중입니다",
    "フォーマット中です。": "포맷 중입니다.",
    "コメントをセーブ中です。": "코멘트 저장 중입니다.",
    "空き容量の確認中です。": "빈 용량 확인 중입니다.",
    "チェック中です。": "체크 중입니다.",
    "このゲームのデータをセーブする為には最低": "이 게임 데이터를 저장하려면 최소",
    "以下の空き容量が必要です。": "이하 빈용량이 필요합니다.",
    "セーブデータ（新規作成）": "세이브데이터（신규작성）",
    "中断データ（新規作成）": "중단데이터（신규작성）",
    "このままゲームを開始しますか？": "이대로 게임을 시작합니까?",
    "空き容量が不足しています。": "빈 용량이 부족합니다.",
    "アクセスできません。": "접근할 수 없습니다.",
    "挿入されていません。": "삽입되지 않았습니다.",
    "と対戦しますか？": "와 대전합니까?",
    "ランキングバトルを中止しますか？": "랭킹배틀을 중지합니까?",
}


def enc(kr):
    o = bytearray()
    i = 0
    while i < len(kr):
        m = T4.match(kr, i)
        if m:
            o += struct.pack(">H", int(m.group(1), 16))
            i = m.end()
            continue
        m = T2.match(kr, i)
        if m:
            o.append(int(m.group(1), 16))
            i = m.end()
            continue
        c = kr[i]
        if c == "\x80":
            o.append(0x80)
            i += 1
        elif c in invkr:
            o += struct.pack(">H", invkr[c])
            i += 1
        elif ord(c) < 0x80:
            o.append(ord(c))
            i += 1
        else:
            return None, c
        i += 1 if False else 0  # noop (i already advanced)
    return bytes(o), None


def translate_entry(jp):
    """태그 경계로 분해해 조각 번역, 미사전 조각 리스트 반환."""
    out = []
    missing = []
    pos = 0
    for m in TAG.finditer(jp):
        seg = jp[pos:m.start()]
        if seg:
            t, miss = tr_piece(seg)
            out.append(t)
            if miss:
                missing.append(miss)
        out.append(m.group(0))
        pos = m.end()
    seg = jp[pos:]
    if seg:
        t, miss = tr_piece(seg)
        out.append(t)
        if miss:
            missing.append(miss)
    return "".join(out), missing


def tr_piece(seg):
    pre = ""
    body = seg
    # \x80 접두/공백 보존
    while body and body[0] in ("\x80", " ", "　"):
        pre += body[0]
        body = body[1:]
    post = ""
    while body and body[-1] in (" ", "　"):
        post = body[-1] + post
        body = body[:-1]
    if not body:
        return seg, None
    if body in PIECE:
        return pre + PIECE[body] + post, None
    # 일본어 문자 없으면 그대로 (숫자/기호)
    if not any(("぀" <= c <= "ヿ") or ("一" <= c <= "鿿") for c in body):
        return seg, None
    return seg, body


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

    rows = json.load(open("work/menu_jp/keyhelp_remain.json", encoding="utf-8"))
    dat = bytearray(open(args.dat, "rb").read())
    base = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))[SLOT]
    src = open("DAT.BIN", "rb").read()
    sbase = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))[SLOT]

    ok = skip = over = missing_n = err = 0
    probs = []
    all_missing = {}
    for r in rows:
        ro, L, jp = r["roff"], r["len"], r["jp"]
        if not r["cn_tr"] or ro in SKIP_ROFF:
            skip += 1
            continue
        # 안전: 대상이 아직 원본과 동일한지 (이미 다른 패치가 만졌으면 스킵)
        if bytes(dat[base + ro:base + ro + L]) != src[sbase + ro:sbase + ro + L]:
            skip += 1
            continue
        kr, miss = translate_entry(jp)
        if miss:
            missing_n += 1
            for mseg in miss:
                all_missing[mseg] = all_missing.get(mseg, 0) + 1
            continue
        e, badch = enc(kr)
        if e is None:
            err += 1
            probs.append((ro, f"인코딩불가 {badch!r}", kr))
            continue
        if len(e) > L:
            over += 1
            probs.append((ro, f"초과 {len(e)}>{L}", kr))
            continue
        if not args.check:
            dat[base + ro:base + ro + L] = e + b" " * (L - len(e))
        ok += 1

    print(f"[{'검사' if args.check else '적용'}] OK {ok} / 스킵 {skip} / 미사전 {missing_n} / 초과 {over} / 에러 {err}")
    if all_missing:
        print("미사전 조각:")
        for s, n in sorted(all_missing.items(), key=lambda x: -x[1]):
            print(f"  {n:2}x {s!r}")
    for ro, m, k in probs[:20]:
        print(f"  +{ro:#x}: {m}  {k[:40]!r}")
    if not args.check and ok:
        open(args.dat, "wb").write(bytes(dat))
        print(f"[OK] {args.dat} 슬롯{SLOT} 잔여 {ok}건 (크기·널구조 불변 {len(dat)}B)")


if __name__ == "__main__":
    main()
