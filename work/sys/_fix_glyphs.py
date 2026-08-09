#!/usr/bin/env python3
# 시스템 문자열용 글리프 정리 (work/mt/_fix_glyphs.py 의 시스템 버전).
#  - 코드테이블(TBL)에 없어 insert 시 cp932 에러를 내는 문자 교정 (· U+00B7 -> ・).
#  - 폰트에 없는 장음 대시(― — ─) 제거, 일본어 장음 ー 제거.
#  - 말줄임표 3점 통일(…+ / ... -> …).
#  - 반복 시스템 문구 축약(용량), 고유명사 표기 통일.
#  - 조합 안 된 낱자(ㅎㅎ/ㅠㅠ) 교정.
#  work/sys/batch_*_kr.json 과 tor_system.xlsx 양쪽에 적용. 멱등.
import glob, json, re
import openpyxl

MTDIR = r"D:\clean_project\work\sys"
XLSX = r"D:\clean_project\tor_system.xlsx"

SUBS = [
    ("ㅎㅎㅎㅎㅎㅎ", "후후후후후후"),
    ("ㅎㅎㅎ", "후후후"),
    ("ㅎㅎ", "후후"),
    ("ㅠㅠ", ""),
    ("―", ""), ("—", ""), ("─", ""),
    ("，", ","),
    ("·", "・"),   # U+00B7 -> U+30FB (TBL에 있음). cp932 에러 방지.
    ("ー", ""),     # 일본어 장음
    # 반복 시스템 문구 축약 (전 씬 일괄, 용량 직결)
    ("동료가 되었습니다", "동료가 됐습니다"),
    ("휴식하시겠습니까?", "쉬시겠습니까?"),
    ("갈드를 손에 넣었습니다", "갈드를 얻었습니다"),
    ("포플러", "포플라"),
]
ELLIPSIS = re.compile(r"…+")
ASCII_DOTS = re.compile(r"\.{3,}")
FORCE = [("포르스", "포스"), ("폴스", "포스")]


def clean(s):
    for a, b in SUBS:
        s = s.replace(a, b)
    s = ASCII_DOTS.sub("…", s)
    s = ELLIPSIS.sub("…", s)
    for a, b in FORCE:
        s = s.replace(a, b)
    return s


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

wb = openpyxl.load_workbook(XLSX)
ws = wb.active
x_lines = 0
for row in ws.iter_rows(min_row=2):
    sc, idv = row[0].value, row[1].value
    if sc is None or idv is None or str(idv).strip() == "":
        continue
    kr = row[6].value or ""
    if not kr:
        continue
    new = clean(kr)
    if new != kr:
        row[6].value = new
        x_lines += 1
wb.save(XLSX)
print(f"[엑셀] {x_lines}줄 정리")
