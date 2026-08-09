#!/usr/bin/env python3
# 시스템 배치 결과(batch_NNN_kr.json) 클리닝.
#  (1) kr 에 일본어 가나/한자가 남은 줄(= 번역 안 된 디버그 라벨 또는 번역 누락)은
#      kr 을 빈칸으로 만든다 -> 빌드가 CN 원문을 그대로 유지(인코딩에러/글리프깨짐 회피).
#      * 태그 안(<...>)의 내용은 검사 제외. ・(U+30FB), ー(U+30FC)는 기호라 제외.
#  (2) 통계 리포트.
# 파일을 제자리에서 덮어쓴다. 원본이 필요하면 먼저 백업.
import json, glob, os, re, sys

MTDIR = r"D:\clean_project\work\sys"
TAG = re.compile(r"<[^>]+>")
JPCHAR = re.compile(r"[぀-ゟ゠-ヺ㐀-鿿]")  # 히라가나+가타카나(・ー제외)+한자

apply = "--apply" in sys.argv
total_blanked = total_lines = 0
per = []
for f in sorted(glob.glob(os.path.join(MTDIR, "batch_[0-9][0-9][0-9]_kr.json"))):
    data = json.load(open(f, encoding="utf-8"))
    blanked = 0
    for r in data:
        total_lines += 1
        kr = r.get("kr", "")
        if kr and JPCHAR.search(TAG.sub("", kr)):
            if apply:
                r["kr"] = ""
            blanked += 1
    if blanked:
        per.append((os.path.basename(f), blanked))
    total_blanked += blanked
    if apply:
        json.dump(data, open(f, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

mode = "적용됨" if apply else "DRY-RUN (적용하려면 --apply)"
print(f"[{mode}] 전체 {total_lines}줄 중 일본어잔존 {total_blanked}줄 -> 빈칸(CN원문 유지)")
for name, b in per:
    print(f"  {name}: {b}줄")
