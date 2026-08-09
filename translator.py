#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translator.py — Tales of Rebirth 한글화 웹 번역 에디터 (개선판)

단일 파일, 표준 라이브러리만 (설치 불필요).
translation/{scene}.json 을 읽고 쓰는 로컬 웹 에디터.

개선 기능:
  - 사이드바: 전체 진행률 바 + 씬 검색 + 미완료만 보기 + 지역별 그룹(선택)
  - 대사 편집: JP 원문 + EN 참조 + KR 입력
  - 태그 툴바: 원문 태그를 클릭 한 번에 삽입 (색상/화자 태그 실수 방지)
  - 태그 QA: 원문 태그 누락/괄호 불균형 실시간 경고 + 씬 단위 요약 + 빌드 가드
  - 미번역 탐색: '다음 미번역' 버튼(Ctrl+Enter), 미번역만 필터
  - 자동 저장, 빌드/반영 버튼
  - 단축키: Ctrl+S 저장, Ctrl+B 빌드

선택 파일:
  scenario_map.json  {"4246": {"area":"Sulz Village","order":3}, ...}
    있으면 사이드바에 지역/순서 표시. (없어도 동작)

사용:
  py translator.py
  py translator.py --port 8765 --font 00014_hangul_full.bin
"""
import argparse
import json
import os
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

TRANS_DIR = "translation"
FONT = "00014_hangul_full.bin"


def _utf8_env():
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, env=_utf8_env())
        out = r.stdout.decode('utf-8', errors='replace') + r.stderr.decode('utf-8', errors='replace')
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def load_scenario_map():
    p = Path("scenario_map.json")
    if p.exists():
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def list_scenes():
    d = Path(TRANS_DIR)
    smap = load_scenario_map()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        lines = data.get("lines", [])
        total = len(lines)
        done = sum(1 for l in lines if (l.get("kr") or "").strip())
        sc = str(data.get("scene", p.stem))
        meta = smap.get(sc, {})
        out.append({"scene": sc, "total": total, "done": done,
                    "area": meta.get("area", ""), "order": meta.get("order", 99999)})
    out.sort(key=lambda s: (s["area"], s["order"], s["scene"]))
    return out


def load_scene(scene):
    p = Path(TRANS_DIR) / f"{scene}.json"
    if not p.exists():
        return None
    return json.load(open(p, encoding="utf-8"))


def save_scene(scene, data):
    p = Path(TRANS_DIR) / f"{scene}.json"
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>ToR 한글화 에디터</title>
<style>
  :root { --bg:#1a1b26; --panel:#24283b; --fg:#c0caf5; --acc:#7aa2f7; --done:#9ece6a; --muted:#565f89; --border:#3b4261; --warn:#e0af68; --err:#f7768e; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:'Malgun Gothic',sans-serif; background:var(--bg); color:var(--fg); display:flex; height:100vh; }
  #sidebar { width:270px; background:var(--panel); border-right:1px solid var(--border); overflow-y:auto; flex-shrink:0; display:flex; flex-direction:column; }
  #overall { padding:10px 12px; border-bottom:1px solid var(--border); font-size:12px; }
  .bar { height:8px; background:#1e2030; border-radius:4px; overflow:hidden; margin-top:4px; }
  .bar > div { height:100%; background:var(--done); transition:width .3s; }
  #sctrl { padding:8px 12px; border-bottom:1px solid var(--border); display:flex; gap:6px; flex-direction:column; }
  #sctrl input[type=text] { background:#1e2030; border:1px solid var(--border); border-radius:4px; color:var(--fg); padding:5px 8px; font-size:12px; }
  #sctrl label { font-size:11px; color:var(--muted); display:flex; align-items:center; gap:5px; cursor:pointer; }
  #scenes { flex:1; overflow-y:auto; }
  .area-hd { font-size:11px; color:var(--acc); padding:8px 12px 3px; font-weight:bold; background:#1e2030; position:sticky; top:0; }
  .scene-item { padding:8px 12px; cursor:pointer; border-bottom:1px solid #2a2e42; font-size:13px; display:flex; justify-content:space-between; align-items:center; }
  .scene-item:hover { background:#2f334d; }
  .scene-item.active { background:var(--acc); color:#1a1b26; }
  .prog { font-size:11px; color:var(--muted); }
  .scene-item.active .prog { color:#1a1b26; }
  .done100 { color:var(--done); }
  #main { flex:1; overflow-y:auto; padding:16px; }
  #topbar { display:flex; gap:8px; align-items:center; margin-bottom:12px; flex-wrap:wrap; }
  #topbar h1 { font-size:16px; margin:0; color:var(--acc); }
  #topbar button { background:var(--acc); color:#1a1b26; border:none; border-radius:5px; padding:7px 12px; cursor:pointer; font-weight:bold; font-size:13px; }
  #topbar button:hover { opacity:.85; }
  #topbar button.sec { background:#2f334d; color:var(--fg); }
  #tagsummary { font-size:12px; color:var(--warn); margin-left:auto; }
  #buildlog { display:none; background:#161821; border:1px solid var(--border); border-radius:6px; padding:10px; margin-bottom:12px; font-family:monospace; font-size:12px; white-space:pre-wrap; max-height:200px; overflow-y:auto; color:#a9b1d6; }
  .line { background:var(--panel); border:1px solid var(--border); border-radius:6px; padding:10px; margin-bottom:10px; }
  .line.done { border-left:3px solid var(--done); }
  .line.untrans { border-left:3px solid var(--muted); }
  .line.hasissue { border-left:3px solid var(--err); }
  .line-head { font-size:11px; color:var(--muted); margin-bottom:6px; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  .jp { font-size:14px; color:#a9b1d6; white-space:pre-wrap; padding:6px; background:#1e2030; border-radius:4px; margin-bottom:4px; }
  .en { font-size:12px; color:var(--muted); white-space:pre-wrap; padding:3px 6px; font-style:italic; margin-bottom:4px; }
  textarea { width:100%; background:#1e2030; color:var(--fg); border:1px solid var(--border); border-radius:4px; padding:8px; font-family:inherit; font-size:14px; resize:vertical; min-height:52px; }
  textarea:focus { outline:1px solid var(--acc); }
  .tools { margin-top:5px; display:flex; gap:6px; align-items:center; font-size:11px; color:var(--muted); flex-wrap:wrap; }
  .tools button { background:#2f334d; color:var(--fg); border:1px solid var(--border); border-radius:4px; padding:3px 7px; cursor:pointer; font-size:11px; }
  .tools button:hover { background:var(--acc); color:#1a1b26; }
  .tagbtn { background:#2b3a2b !important; color:#9ece6a !important; }
  .tagbtn.missing { background:#3a2b2b !important; color:#f7768e !important; }
  .info { margin-left:4px; }
  .warn { color:var(--warn); }
  .err { color:var(--err); }
  #status { position:fixed; bottom:10px; right:14px; background:var(--panel); border:1px solid var(--border); padding:6px 12px; border-radius:6px; font-size:12px; opacity:0; transition:opacity .2s; z-index:10; }
  #status.show { opacity:1; }
  kbd { background:#1e2030; border:1px solid var(--border); border-radius:3px; padding:1px 4px; font-size:10px; }
</style></head>
<body>
  <div id="sidebar">
    <div id="overall"><span id="ovtext">전체 진행률</span><div class="bar"><div id="ovbar" style="width:0%"></div></div></div>
    <div id="sctrl">
      <input type="text" id="search" placeholder="씬/지역 검색..." oninput="renderScenes()">
      <label><input type="checkbox" id="incompleteOnly" onchange="renderScenes()"> 미완료 씬만</label>
    </div>
    <div id="scenes"></div>
  </div>
  <div id="main">
    <div id="topbar">
      <h1 id="title">씬을 선택하세요</h1>
      <button id="btnBuild" onclick="buildScene()" style="display:none">🔨 빌드 <kbd>Ctrl+B</kbd></button>
      <button id="btnApply" onclick="applyDat()" style="display:none">📦 게임 반영</button>
      <button id="btnNext" class="sec" onclick="jumpNext()" style="display:none">↓ 다음 미번역</button>
      <label id="filterUnt" style="display:none;font-size:12px;color:var(--muted)"><input type="checkbox" id="untOnly" onchange="renderLines()"> 미번역만</label>
      <span id="tagsummary"></span>
    </div>
    <div id="buildlog"></div>
    <div id="lines"></div>
  </div>
  <div id="status"></div>
<script>
let curScene=null, curData=null, saveTimer=null, sceneList=[];

function toast(m){ const s=document.getElementById('status'); s.textContent=m; s.classList.add('show'); setTimeout(()=>s.classList.remove('show'),1200); }

async function loadScenes(){
  const r=await fetch('/api/scenes'); sceneList=await r.json();
  refreshOverall(); renderScenes();
}

function refreshOverall(){
  let td=0,tt=0; sceneList.forEach(s=>{td+=s.done;tt+=s.total;});
  const pct=tt?Math.round(100*td/tt):0;
  document.getElementById('ovbar').style.width=pct+'%';
  document.getElementById('ovtext').textContent=`전체 ${td}/${tt} (${pct}%)`;
}

function renderScenes(){
  const q=document.getElementById('search').value.trim().toLowerCase();
  const incOnly=document.getElementById('incompleteOnly').checked;
  const box=document.getElementById('scenes'); box.innerHTML='';
  let lastArea=null;
  sceneList.forEach(s=>{
    if(q && !(''+s.scene).toLowerCase().includes(q) && !(s.area||'').toLowerCase().includes(q)) return;
    if(incOnly && s.total>0 && s.done>=s.total) return;
    if(s.area && s.area!==lastArea){
      const h=document.createElement('div'); h.className='area-hd'; h.textContent=s.area; box.appendChild(h); lastArea=s.area;
    }
    const d=document.createElement('div'); d.className='scene-item'; if(s.scene==curScene)d.classList.add('active'); d.dataset.scene=s.scene;
    const pct=s.total?Math.round(100*s.done/s.total):0;
    d.innerHTML=`<span>${s.scene}</span><span class="prog ${pct==100?'done100':''}">${s.done}/${s.total}</span>`;
    d.onclick=()=>selectScene(s.scene);
    box.appendChild(d);
  });
}

async function selectScene(scene){
  curScene=scene;
  document.querySelectorAll('.scene-item').forEach(e=>e.classList.toggle('active',e.dataset.scene==scene));
  const r=await fetch('/api/scene?id='+scene); curData=await r.json();
  document.getElementById('title').textContent='씬 '+scene;
  ['btnBuild','btnApply','btnNext'].forEach(id=>document.getElementById(id).style.display='inline-block');
  document.getElementById('filterUnt').style.display='inline-block';
  document.getElementById('buildlog').style.display='none';
  renderLines();
}

function extractTags(s){ return (s.match(/<[^>]*>/g)||[]).filter(t=>t!=='<nl>'&&t!=='<n>'); }

function lineIssue(l){
  const kr=(l.kr||'');
  if(!kr.trim()) return null;
  if(kr.split('<').length!==kr.split('>').length) return '괄호 불균형';
  const jt=extractTags(l.jp||''), kt=extractTags(kr);
  const missing=jt.filter(t=>!kt.includes(t));
  if(missing.length) return '태그 누락: '+missing.join(' ');
  return null;
}

function renderLines(){
  const untOnly=document.getElementById('untOnly').checked;
  const box=document.getElementById('lines'); box.innerHTML='';
  let issues=0;
  curData.lines.forEach((l,i)=>{
    const kr=(l.kr||''); const done=kr.trim().length>0;
    const issue=lineIssue(l); if(issue) issues++;
    if(untOnly && done) return;
    const div=document.createElement('div');
    div.className='line '+(issue?'hasissue':(done?'done':'untrans'));
    const jp=(l.jp||'').replace(/</g,'&lt;');
    const en=(l.en_lauren||l.en_razor||l.en||'');
    const jtags=[...new Set(extractTags(l.jp||''))];
    let tagbar='';
    jtags.forEach(t=>{
      const has=extractTags(kr).includes(t);
      const esc=t.replace(/</g,'&lt;').replace(/>/g,'&gt;');
      tagbar+=`<button class="tagbtn ${has?'':'missing'}" data-tag="${t.replace(/"/g,'&quot;')}" onclick="insTag(${i},this.getAttribute('data-tag'))">${esc}</button>`;
    });
    div.innerHTML=`
      <div class="line-head"><span>#${l.id}</span><span style="color:var(--acc)">${l.speaker||''}</span>${l.voice?'<span>🔊'+l.voice+'</span>':''}${issue?'<span class="err">⚠ '+issue.replace(/</g,'&lt;')+'</span>':''}</div>
      <div class="jp">${jp}</div>
      ${en?'<div class="en">'+en.replace(/</g,'&lt;')+'</div>':''}
      <textarea data-i="${i}" placeholder="번역 입력...">${kr.replace(/</g,'&lt;')}</textarea>
      <div class="tools">
        <button data-tag="<nl>" onclick="insTag(${i},'<nl>')">&lt;nl&gt; 개행</button>
        ${tagbar}
        <span class="info" data-info="${i}"></span>
      </div>`;
    box.appendChild(div);
  });
  box.querySelectorAll('textarea').forEach(ta=>{
    ta.addEventListener('input',()=>onEdit(ta));
    ta.addEventListener('keydown',e=>{ if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();jumpNext();} });
    updateInfo(ta);
  });
  updateTagSummary(issues);
}

function updateTagSummary(issues){
  document.getElementById('tagsummary').innerHTML = issues ? `⚠ 태그 문제 ${issues}줄` : '';
}

function insTag(i,tag){
  const ta=document.querySelector(`textarea[data-i="${i}"]`);
  if(!ta) return;
  const p=ta.selectionStart;
  ta.value=ta.value.slice(0,p)+tag+ta.value.slice(ta.selectionEnd);
  ta.focus(); ta.selectionStart=ta.selectionEnd=p+tag.length;
  onEdit(ta);
}

function updateInfo(ta){
  const i=ta.dataset.i; const info=document.querySelector(`.info[data-info="${i}"]`);
  if(!info) return;
  const v=ta.value; const lines=v.split('<nl>');
  const maxlen=Math.max(...lines.map(x=>x.replace(/<[^>]*>/g,'').length));
  let msg=`${lines.length}줄·최대 ${maxlen}자`;
  if(maxlen>20) msg+=' <span class="warn">⚠ 길수있음</span>';
  info.innerHTML=msg;
}

function onEdit(ta){
  const i=ta.dataset.i; curData.lines[i].kr=ta.value;
  updateInfo(ta);
  const div=ta.closest('.line'); const issue=lineIssue(curData.lines[i]);
  const done=ta.value.trim().length>0;
  div.className='line '+(issue?'hasissue':(done?'done':'untrans'));
  const head=div.querySelector('.line-head');
  let ex=head.querySelector('.err'); if(ex) ex.remove();
  if(issue){ const s=document.createElement('span'); s.className='err'; s.textContent='⚠ '+issue; head.appendChild(s); }
  div.querySelectorAll('.tagbtn').forEach(b=>{
    const t=b.getAttribute('data-tag');
    b.classList.toggle('missing', !extractTags(ta.value).includes(t));
  });
  let issues=0; curData.lines.forEach(l=>{if(lineIssue(l))issues++;}); updateTagSummary(issues);
  clearTimeout(saveTimer); saveTimer=setTimeout(save,600);
}

function jumpNext(){
  const tas=[...document.querySelectorAll('textarea')];
  const cur=document.activeElement;
  let start=tas.indexOf(cur)+1; if(start<=0)start=0;
  for(let k=0;k<tas.length;k++){
    const idx=(start+k)%tas.length;
    if(!tas[idx].value.trim()){ tas[idx].focus(); tas[idx].scrollIntoView({block:'center',behavior:'smooth'}); return; }
  }
  toast('미번역 없음');
}

async function save(){
  if(!curScene) return;
  await fetch('/api/save?id='+curScene,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(curData)});
  toast('저장됨');
  const s=sceneList.find(x=>x.scene==curScene);
  if(s){ s.done=curData.lines.filter(l=>(l.kr||'').trim()).length; }
  refreshOverall(); renderScenes();
}

function showLog(t){ const l=document.getElementById('buildlog'); l.style.display='block'; l.textContent=t; }

async function buildScene(){
  if(!curScene) return;
  await save();
  let issues=0; curData.lines.forEach(l=>{if(lineIssue(l))issues++;});
  if(issues && !confirm(`태그 문제가 ${issues}줄 있습니다. 그래도 빌드할까요?\n(태그 누락은 게임 크래시 원인이 될 수 있습니다)`)) return;
  showLog('빌드 중... (씬 '+curScene+')');
  const r=await fetch('/api/build?id='+curScene,{method:'POST'});
  const j=await r.json();
  showLog((j.ok?'✅ 빌드 성공\n':'❌ 빌드 실패\n')+j.log);
  toast(j.ok?'빌드 완료':'빌드 실패');
}

async function applyDat(){
  showLog('게임에 반영 중... (DAT 재패킹 - 시간이 걸립니다)');
  const r=await fetch('/api/apply?id='+curScene,{method:'POST'});
  const j=await r.json();
  showLog((j.ok?'✅ 반영 완료 (DAT_cn_new.BIN)\n':'❌ 실패\n')+j.log);
  toast(j.ok?'반영 완료':'반영 실패');
}

document.addEventListener('keydown',e=>{
  if(e.ctrlKey && (e.key==='s'||e.key==='S')){ e.preventDefault(); save(); }
  if(e.ctrlKey && (e.key==='b'||e.key==='B')){ e.preventDefault(); buildScene(); }
});

loadScenes();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
        elif u.path == "/api/scenes":
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(list_scenes(), ensure_ascii=False).encode("utf-8"))
        elif u.path == "/api/scene":
            scene = parse_qs(u.query).get("id", [""])[0]
            data = load_scene(scene)
            if data is None:
                self._send(404, "application/json", b'{"error":"not found"}')
            else:
                self._send(200, "application/json; charset=utf-8",
                           json.dumps(data, ensure_ascii=False).encode("utf-8"))
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        scene = parse_qs(u.query).get("id", [""])[0]
        if u.path == "/api/save":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            save_scene(scene, data)
            self._send(200, "application/json", b'{"ok":true}')
        elif u.path == "/api/build":
            ok, log = run_cmd(["py", "build_scene.py", "--scene", str(scene)])
            self._send(200, "application/json; charset=utf-8",
                       json.dumps({"ok": ok, "log": log}, ensure_ascii=False).encode("utf-8"))
        elif u.path == "/api/apply":
            ok, log = run_cmd(["py", "build_dat.py", "--all", "--font", FONT])
            self._send(200, "application/json; charset=utf-8",
                       json.dumps({"ok": ok, "log": log}, ensure_ascii=False).encode("utf-8"))
        else:
            self._send(404, "text/plain", b"not found")


def main():
    global TRANS_DIR, FONT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--trans-dir", default="translation")
    ap.add_argument("--font", default="00014_hangul_full.bin")
    args = ap.parse_args()
    TRANS_DIR = args.trans_dir
    FONT = args.font

    Path(TRANS_DIR).mkdir(exist_ok=True)
    url = f"http://localhost:{args.port}"
    print(f"[i] 번역 에디터: {url}")
    print(f"[i] 번역 폴더: {Path(TRANS_DIR).resolve()}")
    print(f"[i] 단축키: Ctrl+S 저장 / Ctrl+B 빌드 / Ctrl+Enter 다음 미번역")
    print(f"[i] 종료: Ctrl+C")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n종료.")


if __name__ == "__main__":
    main()
