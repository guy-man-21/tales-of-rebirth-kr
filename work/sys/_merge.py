#!/usr/bin/env python3
# work/sys/batch_NNN_kr.json 결과를 tor_system.xlsx Korean 열에 병합 + 태그 검증.
# (work/mt/_merge.py 의 시스템 문자열 버전)
import openpyxl, json, re, glob, os

XLSX = r"D:\clean_project\tor_system.xlsx"
MTDIR = r"D:\clean_project\work\sys"
TAG = re.compile(r"<[^>]+>")

kr = {}
bad_files = []
got_batches = 0
for f in sorted(glob.glob(os.path.join(MTDIR, "batch_*_kr.json"))):
    try:
        data = json.load(open(f, encoding="utf-8"))
        for r in data:
            kr[(int(r["scene"]), str(r["id"]))] = r["kr"]
        got_batches += 1
    except Exception as e:
        bad_files.append((os.path.basename(f), f"{type(e).__name__}: {e}"))

expected = sorted(glob.glob(os.path.join(MTDIR, "batch_[0-9][0-9][0-9].json")))
missing = []
for inp in expected:
    n = os.path.basename(inp).replace(".json", "")
    if not os.path.exists(os.path.join(MTDIR, n + "_kr.json")):
        missing.append(n)

wb = openpyxl.load_workbook(XLSX)
ws = wb.active
injected = tagwarn = 0
warn_samples = []
for row in ws.iter_rows(min_row=2):
    sc, idv = row[0].value, row[1].value
    if sc is None or idv is None or str(idv).strip() == "":
        continue
    key = (int(sc), str(idv))
    if key not in kr:
        continue
    if row[6].value and str(row[6].value).strip():
        continue  # 기존 번역 보존
    jp = row[5].value or ""
    k = kr[key]
    if sorted(TAG.findall(jp)) != sorted(TAG.findall(k)):
        tagwarn += 1
        if len(warn_samples) < 15:
            warn_samples.append((sc, idv, TAG.findall(jp), TAG.findall(k)))
    row[6].value = k
    injected += 1
wb.save(XLSX)

print(f"[병합] 결과배치 {got_batches}개, 주입 {injected}줄, 태그경고 {tagwarn}건")
if missing:
    print(f"[!] 결과없는 배치 {len(missing)}개: {missing}")
if bad_files:
    print(f"[!] 손상 결과파일 {len(bad_files)}개: {bad_files}")
if warn_samples:
    print("[태그경고 샘플]")
    for sc, idv, a, b in warn_samples:
        print(f"  씬{sc} id{idv}: jp{a} != kr{b}")
