#!/usr/bin/env python3
# ============================================================
#  qa_check.py -- 빌드 전 일괄 검사
#
#  1) 채움률 / 미번역 씬
#  2) 태그 검증 (jp vs kr 태그 집합 불일치 -> 크래시 원인 1순위)
#  3) 폰트 커버리지 (2350 음절 밖 한글 / 글리프 없을 수 있는 비ASCII 기호)
#  4) 길이 초과 (씬별 kr 총량이 jp보다 큰 곳 -> THEIRSCE 용량 초과 위험)
#
#  사용: py qa_check.py [--xlsx tor_dialogue.xlsx] [--top 20]
# ============================================================
import argparse
import collections
import re

import openpyxl

TAG = re.compile(r"<[^>]+>")

ap = argparse.ArgumentParser()
ap.add_argument("--xlsx", default="tor_dialogue.xlsx")
ap.add_argument("--syllables", default="hangul_syllables.txt")
ap.add_argument("--top", type=int, default=20, help="길이초과 상위 N개 씬")
args = ap.parse_args()

ws = openpyxl.load_workbook(args.xlsx, read_only=True).active
rows = []
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[1] is None or str(r[1]).strip() == "":
        continue  # 씬 헤더행
    rows.append({"scene": int(r[0]), "id": str(r[1]),
                 "jp": r[5] or "", "kr": r[6] or ""})

# --- 1) 채움률 ---
filled = [r for r in rows if r["kr"].strip()]
empty_scenes = sorted({r["scene"] for r in rows if not r["kr"].strip()})
print("=" * 60)
print(f"[1] 채움률: {len(filled)}/{len(rows)} "
      f"({len(filled)*100//max(len(rows),1)}%)")
if empty_scenes:
    print(f"    미번역 씬 {len(empty_scenes)}개: "
          f"{empty_scenes[:12]}{' ...' if len(empty_scenes) > 12 else ''}")

# --- 2) 태그 ---
bad = []
for r in filled:
    if sorted(TAG.findall(r["jp"])) != sorted(TAG.findall(r["kr"])):
        bad.append(r)
print("=" * 60)
print(f"[2] 태그 불일치: {len(bad)}줄  {'[OK]' if not bad else '[!] 크래시 위험'}")
for r in bad[:10]:
    print(f"    s{r['scene']} #{r['id']}: jp{TAG.findall(r['jp'])} "
          f"!= kr{TAG.findall(r['kr'])}")

# --- 3) 폰트 커버리지 ---
syl = {ch for ch in open(args.syllables, encoding="utf-8").read()
       if "가" <= ch <= "힣"}
miss_syl = collections.Counter()
odd_chars = collections.Counter()
for r in filled:
    body = TAG.sub("", r["kr"])  # 태그 안 문자는 렌더링 대상 아님
    for ch in body:
        if "가" <= ch <= "힣":
            if ch not in syl:
                miss_syl[ch] += 1
        elif "ㄱ" <= ch <= "ㅣ":       # 조합 안 된 낱자(ㅡ, ㅋ 등) - 폰트에 없음
            odd_chars[ch] += 1
        elif ord(ch) > 0x2000 and not ("가" <= ch <= "힣"):
            # 원문에도 있는 기호는 정상. 원문에 없는 기호만 의심.
            if ch not in "".join(x["jp"] for x in filled[:0]):
                odd_chars[ch] += 1
print("=" * 60)
print(f"[3] 폰트: 2350 밖 한글 음절 {len(miss_syl)}종 "
      f"{'[OK]' if not miss_syl else '[!] 글자 빠짐'}")
if miss_syl:
    print("    " + " ".join(f"{c}x{n}" for c, n in miss_syl.most_common(30)))

# 원문에 쓰인 기호는 이미 폰트에 있는 것 -> 그것과 비교해 새로 생긴 기호만 경고
jp_chars = set()
for r in rows:
    jp_chars.update(TAG.sub("", r["jp"]))
new_syms = {c: n for c, n in odd_chars.items() if c not in jp_chars}
print(f"    원문에 없던 기호 {len(new_syms)}종 "
      f"{'[OK]' if not new_syms else '[!] 글리프 없을 수 있음'}")
if new_syms:
    for c, n in sorted(new_syms.items(), key=lambda x: -x[1])[:20]:
        print(f"      U+{ord(c):04X} {c!r} x{n}")

# --- 4) 길이 ---
per_scene = collections.defaultdict(lambda: [0, 0])
for r in filled:
    jp_len = len(TAG.sub("", r["jp"]))
    kr_len = len(TAG.sub("", r["kr"]))
    per_scene[r["scene"]][0] += jp_len
    per_scene[r["scene"]][1] += kr_len
over = [(sc, j, k, k - j, (k - j) * 100 // max(j, 1))
        for sc, (j, k) in per_scene.items() if k > j]
over.sort(key=lambda x: -x[3])
tot_jp = sum(v[0] for v in per_scene.values())
tot_kr = sum(v[1] for v in per_scene.values())
print("=" * 60)
print(f"[4] 길이: 전체 jp {tot_jp} -> kr {tot_kr} "
      f"({(tot_kr-tot_jp)*100//max(tot_jp,1):+d}%)")
print(f"    원문보다 긴 씬 {len(over)}개 / {len(per_scene)}개")
print(f"    상위 {args.top}개 (씬: jp -> kr, 증가):")
for sc, j, k, d, pct in over[:args.top]:
    print(f"      씬 {sc}: {j} -> {k}  (+{d}자, +{pct}%)")
print("=" * 60)
print("주의: THEIRSCE는 바이트 단위 제약. 위는 글자 수 기준 근사치이며,")
print("      실제 초과 여부는 build_scene.py 의 fix_container() 가 판정한다.")
