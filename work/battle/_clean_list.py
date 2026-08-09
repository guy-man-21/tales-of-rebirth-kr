import json, re
rows=json.load(open('work/battle/battle_strings.json',encoding='utf-8'))
TAG=re.compile(r'<[0-9A-F]{4}>')
def clean_jp(s):
    # 끝쪽 제어태그 제거
    return TAG.sub('', s)
translatable=[]
for r in rows:
    jp=r['jp']
    # 바이너리 태그 비율
    tags=TAG.findall(jp)
    core=TAG.sub('',jp)
    # 진짜 텍스트: 코어에 일본어 있고, 태그가 적음(문두/문미 제어정도)
    has_jp=any('぀'<=c<='ヿ' or '一'<=c<='鿿' for c in core)
    if has_jp and len(tags)<=2 and len(core)>=2:
        translatable.append(r)
print(f'전체 {len(rows)}개 중 번역대상(클린) {len(translatable)}개')
print('=== 번역대상 battle help/전투 텍스트 ===')
for r in translatable:
    print(f'  #{r["idx"]:3} CN{r["cn_len"]:3}B: {clean_jp(r["jp"])[:50]!r}')
json.dump(translatable, open('work/battle/battle_translatable.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
