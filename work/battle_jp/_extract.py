#!/usr/bin/env python3
# 슬롯2(압축 ELF 배틀모듈)의 텍스트 영역에서 일본어 문자열 전체 추출.
#  - 제자리 교체용: off(해제데이터 기준) + avail(널 포함 쓸 수 있는 바이트)
#  - battle_work.json 에서 이미 번역된 원문은 kr 미리 채움 (조작힌트 172개)
#  - translation/*.json 의 스토리 대사와 원문이 일치하면 kr 재활용
# 출력: work/battle_jp/slot2_work.json
import glob
import json
import os
import struct
import sys

os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

Tall = json.load(open("tbl_all.json", encoding="utf-8"))
Tall = Tall.get("TBL", Tall)

PTR = 0x126F90
jp = open("DAT.BIN", "rb").read()
eboot = open("ULJS00132_EBOOT.BIN", "rb").read()
ptrs = []
i = 0
while True:
    v = struct.unpack_from("<I", eboot, PTR + i*4)[0]
    if i > 0 and (v < ptrs[-1] or v > len(jp)*1.05):
        break
    ptrs.append(v); i += 1
    if i > 40000:
        break

blob = jp[ptrs[2]:ptrs[3]]
csz = struct.unpack_from("<I", blob, 1)[0]
d = comptolib.decompress_data(blob[:9+csz])
print(f"슬롯2 해제 {len(d)}B")

# 텍스트 영역 (실측: @269585~288704 + 여유)
LO, HI = 268000, 292000


def decstr(dd, off, maxlen=200):
    """널까지 디코드. 코드테이블 밖 2바이트값은 <XXXX> 태그로 보존."""
    s = ""
    i = off
    n = 0
    while i < len(dd) - 1 and n < maxlen:
        c = dd[i]
        if c == 0:
            break
        if c >= 0x81:
            code = (c << 8) | dd[i+1]
            v = Tall.get(f"{code:04X}")
            s += v if v else f"<{code:04X}>"
            i += 2
        elif 0x20 <= c < 0x7f:
            s += chr(c)
            i += 1
        elif c in (0x0a, 0x0d):
            # 제어바이트 - 태그로 보존
            s += f"<{c:02X}>"
            i += 1
        else:
            s += f"<{c:02X}>"
            i += 1
        n += 1
    return s, i


def avail_bytes(dd, off):
    i = off
    while i < len(dd) and dd[i] != 0:
        i += 1
    e = i
    while e < len(dd) and dd[e] == 0:
        e += 1
    return e - off   # 문자열+널패딩 총 공간


def is_texty(s):
    # 히라가나/가타카나 1+ 또는 한자2+ 연속 = 실제 텍스트
    kana = sum(1 for c in s if "぀" <= c <= "ヿ")
    return kana >= 1 and len(s) >= 2


rows = []
i = LO
while i < HI:
    if d[i] == 0:
        i += 1
        continue
    s, ni = decstr(d, i)
    if is_texty(s):
        rows.append({"off": i, "avail": avail_bytes(d, i), "jp": s, "kr": ""})
    i = ni + 1
print(f"텍스트 {len(rows)}개 추출 (@{LO}~{HI})")

# 1) battle_work 재활용 (조작힌트)
bw = json.load(open("work/battle/battle_work.json", encoding="utf-8"))
bw_map = {w["jp"]: (w.get("kr") or "").strip() for w in bw
          if (w.get("kr") or "").strip()}
n_bw = 0
for r in rows:
    if r["jp"] in bw_map:
        r["kr"] = bw_map[r["jp"]]
        r["src"] = "battle_work"
        n_bw += 1

# 2) translation 스토리 대사 재활용 (jp 완전일치)
tr_map = {}
for f in glob.glob("translation/*.json"):
    try:
        data = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    for l in data.get("lines", []):
        jpt = (l.get("jp") or "").strip()
        krt = (l.get("kr") or "").strip()
        if jpt and krt:
            tr_map.setdefault(jpt, krt)
n_tr = 0
for r in rows:
    if r["kr"]:
        continue
    # 슬롯2 는 개행이 <01> 태그. 끝쪽 <01> 반복(패딩)은 제거 후 비교.
    core = r["jp"]
    while core.endswith("<01>"):
        core = core[:-4]
    cands = [core, core.replace("<01>", "\n"), core.replace("<01>", " "),
             core.replace("<01>", "")]
    for c in cands:
        if c in tr_map:
            r["kr"] = tr_map[c]
            r["src"] = "translation"
            n_tr += 1
            break

n_left = sum(1 for r in rows if not r["kr"])
print(f"재활용: battle_work {n_bw} / translation {n_tr} / 미번역 {n_left}")

json.dump(rows, open("work/battle_jp/slot2_work.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("-> work/battle_jp/slot2_work.json")

# 미번역 샘플
print("\n미번역 샘플 30:")
c = 0
for r in rows:
    if not r["kr"] and c < 30:
        print(f"  @{r['off']} av{r['avail']}: {r['jp'][:44]!r}")
        c += 1
