#!/usr/bin/env python3
# ============================================================
#  _fix_glyphs.py -- 폰트에 없는 글자 제거 + 태그 누락 수리
#
#  회수 폰트(2350 음절)에는 한글 음절만 있다. 아래 문자는 글리프가 없어
#  게임에서 빈칸으로 뜬다:
#    - 장음 대시 (U+2015 ―, U+2014 —, U+2500 ─): 일본어 'ー'를 옮기며 쓴 것.
#      한국어에선 불필요하므로 삭제 (글자 수도 줄어 THEIRSCE 용량에 유리).
#    - 조합 안 된 낱자 (ㅎㅎ, ㅠㅠ, ㅡ): 채팅체. 원문 의미에 맞게 교체/삭제.
#    - 전각 쉼표 (U+FF0C ，): ASCII ',' 로.
#
#  또한 수동 번역에서 누락된 <font:80000002> 태그를 복구한다 (씬 4246 #18).
#  전각 모드 태그가 빠지면 문자폭이 깨진다.
#
#  표기 규칙(사용자 지정):
#    - 말줄임표: 일본어는 '……'(6점)이 관례지만 한국어는 '…'(3점) 하나만 쓴다.
#      연속된 … 를 전부 하나로 줄인다. ASCII '...' 도 '…' 로 통일.
#      (덤으로 글자 수가 1만 자 이상 줄어 THEIRSCE 용량에 유리)
#    - フォルス 는 '포스' 로 통일 ('포르스'/'폴스' 금지).
#
#  batch_*_kr.json 과 tor_dialogue.xlsx 양쪽에 적용한다.
#  (배치만 고치면 엑셀에 안 반영되고, 엑셀만 고치면 _sync.py 가 되돌린다)
#  멱등(idempotent) -- 여러 번 돌려도 결과가 같다.
# ============================================================
import glob
import json
import re

import openpyxl

MTDIR = r"D:\clean_project\work\mt"
XLSX = r"D:\clean_project\tor_dialogue.xlsx"

# 순서 중요: 긴 것부터
SUBS = [
    ("ㅎㅎㅎㅎㅎㅎ", "후후후후후후"),   # 원문 ふふふふふふ
    ("ㅎㅎㅎ", "후후후"),
    ("ㅎㅎ", "후후"),
    ("ㅠㅠ", ""),
    ("ㅡ", ""),
    ("―", ""),   # U+2015
    ("—", ""),   # U+2014
    ("─", ""),   # U+2500
    ("，", ","),  # U+FF0C
    # U+00B7 (라틴 가운뎃점) -> U+30FB (원문이 쓰는 가운뎃점).
    # U+00B7 은 코드테이블(TBL)에 없어서 insert 시 cp932 인코딩 에러로 빌드가 죽는다.
    ("·", "・"),
    # 일본어 장음(U+30FC). 코드테이블엔 있지만 한국어 문장에 그대로 찍히면 이상하다.
    # ("들어간다ー!!" -> "들어간다!!")
    ("ー", ""),
    # --- 코드테이블에 없는 한자 (회수 폰트가 그 글리프를 한글로 덮어썼다) ---
    # 남겨두면 insert 가 죽거나(4444: ValueError VariableType) 엉뚱한 한글이 표시된다.
    ("(夕凪)", ""),      # 유나기(夕凪) -> 유나기   (s4274)
    ("(地鳴)", ""),      # 지명(地鳴)   -> 지명     (s4337)
    ("一.", "일."),      # 벽보 항목번호 (s4444)
    ("二.", "이."),
    ("三.", "삼."),
    ("四.", "사."),
    ("五.", "오."),
    # --- 반복 시스템 문구 축약 (전 씬 일괄) ---
    # DAT 레이아웃을 못 바꾸므로 THEIRSCE 가 원본 블롭 크기 안에 들어가야 한다.
    # 초과 씬 134개는 대부분 이 시스템 문구만 있는 짧은 씬이라, 이 3개를 줄이면 해결된다.
    # 반드시 '전 씬'에 적용할 것. 일부 씬만 바꾸면 같은 메시지가 씬마다 다르게 뜬다.
    ("동료가 되었습니다", "동료가 됐습니다"),
    ("휴식하시겠습니까?", "쉬시겠습니까?"),
    ("갈드를 손에 넣었습니다", "갈드를 얻었습니다"),
    # 고유명사 표기 통일 (길이 불변). ポプラ = 포플라 (_style.md 확정)
    ("포플러", "포플라"),
]

# 수동 번역에서 누락된 태그 복구: (scene, id) -> (누락태그, 붙일 위치)
TAG_FIX = {
    (4246, "18"): "<font:80000002>",  # 앞에 붙임
}


ELLIPSIS = re.compile(r"…+")        # 연속 말줄임표 -> 하나
ASCII_DOTS = re.compile(r"\.{3,}")  # ASCII '...' -> '…'
FORCE = [("포르스", "포스"), ("폴스", "포스")]


def clean(s):
    for a, b in SUBS:
        s = s.replace(a, b)
    s = ASCII_DOTS.sub("…", s)
    s = ELLIPSIS.sub("…", s)
    for a, b in FORCE:
        s = s.replace(a, b)
    return s


# --- 1) 배치 파일 ---
n_files = n_lines = 0
for f in sorted(glob.glob(f"{MTDIR}/batch_*_kr.json")):
    data = json.load(open(f, encoding="utf-8"))
    dirty = False
    for r in data:
        kr = r.get("kr", "")
        new = clean(kr)
        if new != kr:
            r["kr"] = new
            n_lines += 1
            dirty = True
    if dirty:
        n_files += 1
        json.dump(data, open(f, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
print(f"[배치] {n_files}개 파일, {n_lines}줄 정리")

# --- 2) 엑셀 ---
wb = openpyxl.load_workbook(XLSX)
ws = wb.active
x_lines = x_tags = 0
for row in ws.iter_rows(min_row=2):
    sc, idv = row[0].value, row[1].value
    if sc is None or idv is None or str(idv).strip() == "":
        continue
    kr = row[6].value or ""
    if not kr:
        continue
    new = clean(kr)
    key = (int(sc), str(idv))
    if key in TAG_FIX:
        tag = TAG_FIX[key]
        if tag not in new:
            new = tag + new
            x_tags += 1
            print(f"  [태그복구] s{sc} #{idv}: {tag} 앞에 추가")
    if new != kr:
        row[6].value = new
        x_lines += 1
wb.save(XLSX)
print(f"[엑셀] {x_lines}줄 정리, 태그복구 {x_tags}건")
