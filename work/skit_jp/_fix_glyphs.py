#!/usr/bin/env python3
# 스킷 batch_*_kr.json 글리프 정리 (본편 work/mt/_fix_glyphs.py 의 스킷판).
#  회수 폰트(2350 음절)에 없는 문자 제거/치환 + 말줄임 3점 통일 + 표기 강제.
#  멱등. 사용: py work\skit_jp\_fix_glyphs.py
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# 순서 중요: 긴 것부터
SUBS = [
    ("ㅎㅎㅎㅎㅎㅎ", "후후후후후후"),
    ("ㅎㅎㅎ", "후후후"),
    ("ㅎㅎ", "후후"),
    ("ㅠㅠ", ""),
    ("ㅡ", ""),
    ("―", ""),   # U+2015
    ("—", ""),   # U+2014
    ("─", ""),   # U+2500
    ("，", ","),  # U+FF0C
    ("·", "・"),  # U+00B7 라틴 가운뎃점: TBL 없음 -> 원문식 ・(U+30FB)
    ("ー", ""),   # 일본어 장음: 한국어 문장엔 불필요
    # 표기 통일 (반복 시스템 문구)
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


def main():
    n_files = n_lines = 0
    for f in sorted(glob.glob(os.path.join(HERE, "batch_*_kr.json"))):
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
            json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[OK] {n_files}개 파일, {n_lines}줄 정리")


if __name__ == "__main__":
    main()
