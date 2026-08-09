import json, re
rows=json.load(open('work/names/names_work.json',encoding='utf-8'))
# 고정 번역 (대사 용어집 표기)
NAMES={
 0:'베이그',1:'마오',2:'유진',3:'애니',4:'티트레이',5:'힐다',
 6:'전투 승리',7:'합체기',
 8:'사레',9:'토마',10:'밀리차',11:'발투',12:'밀하우스트',13:'질바',
 14:'샤오룬',15:'이폰',16:'게오르기아스',17:'율리스',18:'도넬',19:'긴날',20:'도른브',21:'유시아',
 22:'왕국병1',23:'왕국병2',24:'도둑1',25:'도둑2',26:'암살자1',27:'암살자2',
 28:'왕의방패 병사1',29:'왕의방패 병사2',30:'왕의방패 도술사',31:'전투 중 대화',
 146:'타이틀',147:'필드',148:'타운',149:'던전',150:'이벤트',151:'전투',152:'미니게임',
}
n=0
for r in rows:
    idx=r['idx']; jp=r['jp']
    if idx in NAMES:
        r['kr']=NAMES[idx]; n+=1
    elif 'エピソード' in jp:
        # エピソード -> 에피소드, 뒤 태그/번호 보존
        r['kr']=jp.replace('エピソード','에피소드'); n+=1
    else:
        r['kr']=''
json.dump(rows,open('work/names/names_work.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f'번역 채움 {n}개')
for r in rows:
    if r['kr']:
        print(f"  [{r['idx']:3}] {r['jp'][:16]!r} -> {r['kr'][:16]!r}")
