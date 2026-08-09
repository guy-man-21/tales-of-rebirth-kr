#!/usr/bin/env python3
# ============================================================
#  _normalize.py -- MT 결과 표기 통일 (batch_*_kr.json 전체)
#
#  1) 기호: 전각 !? -> 반각 !? (기존 코퍼스 다수 관행: 반각 약 10000 vs 전각 약 2300)
#  2) 고유명사: 배치마다 갈린 표기를 확정 표기로 통일
#
#  단순 문자열 치환은 위험하다. 두 가지를 반드시 처리한다:
#
#  (a) 단어 경계 -- '학'->'하크' 를 무작정 하면 '고고학'이 '고고하크'가 된다.
#      이름 앞뒤가 다른 한글 음절이면 그건 이름이 아니라 딴 단어의 일부다.
#      앞: 한글이면 스킵. 뒤: 한글이면 '알려진 조사'일 때만 허용.
#
#  (b) 조사 -- '핵'(받침O)을 '하크'(받침X)로 바꾸면 뒤따르는 조사도 바뀌어야 한다.
#      핵을->하크를, 핵이->하크가, 학이라는->하크라는.
#      반대로 '히토'(받침X)->'사람'(받침O)이면 히토는->사람은.
#      새 이름의 받침 유무에 맞춰 조사를 자동 교정한다.
#
#  사용:
#    py work\mt\_normalize.py            # dry-run (변경 미리보기만)
#    py work\mt\_normalize.py --apply    # 실제 파일 수정
# ============================================================
import argparse
import glob
import json
import os

os.chdir(r"D:\clean_project")
MTDIR = "work/mt"

# 원문 카타카나/한자 -> (확정표기, [교체할 변이들])
# 확정 근거: 기존 코퍼스 다수 표기.
# 예외 ドバル: '도발'(17)이 다수지만 한국어 일반명사 '도발'과 충돌해 오독되므로 '도바르'.
TERMS = [
    ("バイラス",     "바이라스", ["바이러스"]),
    ("ハック",       "하크",     ["핵", "학"]),
    ("ワルトゥ",     "발투",     ["와르투", "왈투"]),
    ("ラジルダ",     "라질다",   ["라지르다"]),
    ("バルカ",       "발카",     ["바르카"]),
    ("ドバル",       "도바르",   ["도발"]),
    ("エリクシール", "엘릭서",   ["엘릭시르"]),
    ("ナッツ",       "나츠",     ["낫츠"]),
    ("ガラルド",     "갈라르드", ["가라르드", "가랄드"]),
    ("ヒト",         "사람",     ["히토"]),
    ("聖なる王",     "성왕",     ["성스러운 왕"]),
]

# 조사 쌍: (받침O 뒤 형태, 받침X 뒤 형태). 긴 것부터 매칭해야 한다.
PARTICLE_PAIRS = [
    ("이라는", "라는"), ("이라고", "라고"), ("이라며", "라며"),
    ("이라도", "라도"), ("이었", "였"), ("이란", "란"),
    ("이랑", "랑"), ("이나", "나"), ("이면", "면"),
    ("이야", "야"), ("이지", "지"), ("으로", "로"),
    ("이다", "다"), ("이라", "라"),
    ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"),
]
# 받침과 무관한 조사/접미 (그대로 둠)
# '인가'(계사 의문)는 받침 유무와 상관없이 그대로. '행/뿐/엔'도 마찬가지.
NEUTRAL = ["한테서", "에게서", "한테", "에게", "까지", "부터", "처럼", "보다",
           "조차", "밖에", "마저", "께서", "께", "도", "만", "에", "의", "와의",
           "인가", "입니다", "뿐", "행", "엔", "엘", "쯤", "발"]

_ALL_PARTICLES = []
for a, b in PARTICLE_PAIRS:
    _ALL_PARTICLES += [a, b]
_ALL_PARTICLES += NEUTRAL
_ALL_PARTICLES.sort(key=len, reverse=True)

PAIR_OF = {}
for a, b in PARTICLE_PAIRS:
    PAIR_OF[a] = (a, b)
    PAIR_OF[b] = (a, b)


def is_hangul(ch):
    return "가" <= ch <= "힣"


def has_batchim(word):
    """마지막 글자에 받침이 있는가."""
    ch = word[-1]
    if not is_hangul(ch):
        return False
    return (ord(ch) - 0xAC00) % 28 != 0


def match_particle(s, i):
    """s[i:] 앞머리에서 가장 긴 조사를 찾는다. 없으면 None."""
    for p in _ALL_PARTICLES:
        if s.startswith(p, i):
            return p
    return None


def replace_name(kr, old, new, report):
    """이름만 정확히 교체하고, 뒤따르는 조사를 새 이름의 받침에 맞춰 고친다."""
    out = []
    i = 0
    batchim = has_batchim(new)
    while i < len(kr):
        if not kr.startswith(old, i):
            out.append(kr[i])
            i += 1
            continue
        # (a) 앞 경계: 앞 글자가 한글이면 다른 단어의 일부 (예: 고고'학')
        if i > 0 and is_hangul(kr[i - 1]):
            out.append(kr[i])
            i += 1
            continue
        j = i + len(old)
        # (a) 뒤 경계: 뒤가 한글인데 아는 조사가 아니면 다른 단어 (예: '학'교)
        nxt = kr[j] if j < len(kr) else ""
        part = match_particle(kr, j) if nxt and is_hangul(nxt) else None
        if nxt and is_hangul(nxt) and part is None:
            report.setdefault("skipped", []).append(kr[max(0, i - 6):j + 6])
            out.append(kr[i])
            i += 1
            continue
        out.append(new)
        i = j
        # (b) 조사 교정
        if part and part in PAIR_OF:
            a, b = PAIR_OF[part]
            fixed = a if batchim else b
            out.append(fixed)
            i += len(part)
    return "".join(out)


ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true", help="실제 파일 수정")
args = ap.parse_args()

jp_map = {}
for f in sorted(glob.glob(f"{MTDIR}/batch_[0-9][0-9][0-9].json")):
    for l in json.load(open(f, encoding="utf-8"))["lines"]:
        jp_map[(int(l["scene"]), str(l["id"]))] = l["jp"]

stats = {"전각!? -> 반각": 0}
for term, canon, _ in TERMS:
    stats[f"{term} -> {canon}"] = 0
samples = []
report = {}
files_changed = 0

for f in sorted(glob.glob(f"{MTDIR}/batch_*_kr.json")):
    data = json.load(open(f, encoding="utf-8"))
    dirty = False
    for r in data:
        kr = r.get("kr", "")
        if not kr:
            continue
        orig = kr
        jp = jp_map.get((int(r["scene"]), str(r["id"])), "")

        n_sym = kr.count("！") + kr.count("？")
        if n_sym:
            stats["전각!? -> 반각"] += n_sym
            kr = kr.replace("！", "!").replace("？", "?")

        for term, canon, variants in TERMS:
            if term not in jp:
                continue
            for v in variants:
                if v not in kr:
                    continue
                before = kr
                kr = replace_name(kr, v, canon, report)
                if kr != before:
                    stats[f"{term} -> {canon}"] += 1
                    if len(samples) < 40:
                        samples.append((r["scene"], r["id"], term, v, canon,
                                        before.replace("\n", " ")[:58],
                                        kr.replace("\n", " ")[:58]))
        if kr != orig:
            r["kr"] = kr
            dirty = True
    if dirty:
        files_changed += 1
        if args.apply:
            json.dump(data, open(f, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)

print("[치환 통계]")
for k, v in stats.items():
    if v:
        print(f"  {k:24s} {v}")
print(f"\n변경된 파일 {files_changed}개")

skipped = report.get("skipped", [])
if skipped:
    print(f"\n[단어 경계로 스킵 - 이름이 아니라 딴 단어였음 {len(skipped)}건]")
    for s in sorted(set(skipped))[:15]:
        print(f"  ...{s}...")

if samples:
    print(f"\n[변경 샘플 {len(samples)}건 - 조사 교정 확인]")
    for sc, i, term, v, canon, before, after in samples:
        print(f"  s{sc} #{i} [{v}->{canon}]")
        print(f"     - {before}")
        print(f"     + {after}")

if not args.apply:
    print("\n*** DRY-RUN. 적용하려면 --apply ***")
