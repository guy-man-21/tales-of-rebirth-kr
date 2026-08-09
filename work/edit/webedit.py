# -*- coding: utf-8 -*-
# 번역 편집 웹 UI (2026-07-25). edit.py 의 검색/검증/적용 엔진을 브라우저로.
#  실행: py work\edit\webedit.py   -> http://localhost:8787 자동 오픈
#  종료: 콘솔에서 Ctrl+C
import importlib.util
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("edit", os.path.join(HERE, "edit.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)          # os.chdir 프로젝트 루트 포함

S = E.load_sources()
def _grp(x):
    if x["src"] == "scene":
        return f"씬 {x['scene']}"
    if x["src"] == "skit":
        return f"스킷 {x['scene']}"
    if x["src"] == "slot2":
        return "슬롯2 (배틀)"
    if x["src"] == "menu":
        return "메뉴 (슬롯3960)"
    if x["src"] == "bb":
        return "배틀북"
    f = x.get("file", "")
    r = x["ref"]
    if "eboot_work" in f:
        cat = r.get("cat", "")
        return {"menu": "EBOOT 버튼/메뉴", "title": "EBOOT 제목/콘텐츠", "skit": "EBOOT 스킷제목",
                "nav": "EBOOT 네비", "name": "EBOOT 화자명", "skill": "EBOOT 스킬"}.get(cat, "EBOOT 기타")
    if "item_work" in f:
        return "아이템"
    if "cbatch" in f or "dbatch" in f:
        return "EBOOT 콘텐츠(배치)"
    if "rbatch" in f:
        return "EBOOT 잔여"
    if "eboot_bh" in f:
        return "배틀 헬프"
    return "기타"
for _x in S:
    _x["grp"] = _grp(_x)
GROUPS = {}
for _i, _x in enumerate(S):
    GROUPS.setdefault(_x["grp"], []).append(_i)
def _grpsort(g):
    if g.startswith("씬 "):
        return (0, int(g[2:]))
    if g.startswith("스킷 "):
        return (1, int(g[3:]))
    return (2, 0)
GLIST = sorted(GROUPS.keys(), key=_grpsort)
LOCK = threading.Lock()
DIRTY = {"scenes": set(), "rows": [], "slot2": False, "skit": set()}

HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>ToR 번역 편집</title>
<style>
 body{font-family:'Malgun Gothic',sans-serif;margin:0;background:#1e2127;color:#d8dee9}
 header{padding:10px 16px;background:#14161a;display:flex;gap:12px;align-items:center;position:sticky;top:0}
 header h1{font-size:15px;margin:0;color:#88c0d0;white-space:nowrap}
 #q{flex:1;padding:8px 10px;font-size:14px;background:#2a2e37;border:1px solid #444;color:#eee;border-radius:6px}
 #pend{font-size:12px;color:#ebcb8b;white-space:nowrap}
 button{padding:8px 14px;border:0;border-radius:6px;background:#5e81ac;color:#fff;font-size:13px;cursor:pointer}
 button:disabled{background:#444;color:#888}
 button.warn{background:#bf616a}
 main{display:flex;height:calc(100vh - 54px)}
 #side{width:46%;display:flex;flex-direction:column;border-right:1px solid #333}
 #tabs{padding:6px 10px;background:#191c21;display:flex;gap:6px}
 .tab{background:#2a2e37;color:#aaa;padding:5px 12px}
 .tab.on{background:#5e81ac;color:#fff}
 #list{flex:1;overflow-y:auto}
 .grp{padding:8px 14px;border-bottom:1px solid #2a2d33;cursor:pointer;font-size:13px;display:flex;justify-content:space-between}
 .grp:hover{background:#262a31}
 .grp .n{color:#8a919e;font-size:11px}
 .hit{padding:8px 12px;border-bottom:1px solid #2a2d33;cursor:pointer;font-size:13px}
 .hit:hover{background:#262a31}.hit.sel{background:#2e3440}
 .hit .key{color:#a3be8c;font-size:11px}
 .hit .jp{color:#8a919e;white-space:pre-wrap;word-break:break-all}
 .hit .kr{color:#e5e9f0;white-space:pre-wrap;word-break:break-all}
 #panel{flex:1;padding:14px 18px;overflow-y:auto}
 #panel .jp{background:#262a31;padding:10px;border-radius:6px;white-space:pre-wrap;word-break:break-all;color:#b8c0cc;font-size:14px}
 textarea{width:100%;min-height:110px;background:#2a2e37;color:#eceff4;border:1px solid #555;border-radius:6px;
          font-size:15px;padding:10px;box-sizing:border-box;font-family:inherit}
 .meta{font-size:12px;color:#8a919e;margin:6px 0}
 #vres{font-size:13px;margin:8px 0;white-space:pre-wrap}
 #vres .err{color:#bf616a} #vres .warn{color:#ebcb8b} #vres .ok{color:#a3be8c}
 #log{background:#14161a;padding:10px;border-radius:6px;font-size:12px;white-space:pre-wrap;color:#a3be8c;
      max-height:220px;overflow-y:auto;margin-top:12px}
 .muted{color:#666;font-size:12px}
</style></head><body>
<header>
 <h1>ToR 번역 편집</h1>
 <input id="q" placeholder="화면에서 본 문구 검색 (한글/일본어)" autofocus>
 <span id="pend"></span>
 <button id="applyBtn" class="warn" onclick="applyAll()">적용+롬배치</button>
</header>
<main>
 <div id="side">
  <div id="tabs">
   <button id="tabS" class="tab on" onclick="mode('s')">검색</button>
   <button id="tabB" class="tab" onclick="mode('b')">목록</button>
   <button id="backBtn" style="display:none" onclick="showGroups()">← 목록</button>
  </div>
  <div id="list"><div class="muted" style="padding:14px">검색어를 입력하세요 (Enter)</div></div>
 </div>
 <div id="panel"><div class="muted">왼쪽에서 항목을 선택하세요</div></div>
</main>
<script>
let hits=[], cur=null, MODE='s';
const $=id=>document.getElementById(id);
$('q').addEventListener('keydown',e=>{if(e.key==='Enter'){if(MODE==='s')search();else loadGroups();}});
function mode(m){MODE=m;$('tabS').classList.toggle('on',m==='s');$('tabB').classList.toggle('on',m==='b');
 $('backBtn').style.display='none';
 if(m==='b'){$('q').placeholder='그룹 필터 (예: 씬 4489, 슬롯2, 아이템)';loadGroups();}
 else{$('q').placeholder='화면에서 본 문구 검색 (한글/일본어)';$('list').innerHTML='<div class="muted" style="padding:14px">검색어를 입력하세요 (Enter)</div>';}}
async function loadGroups(){
 const q=$('q').value.trim();
 const r=await fetch('/api/groups?q='+encodeURIComponent(q)); const gs=await r.json();
 $('backBtn').style.display='none';
 const L=$('list'); L.innerHTML='';
 gs.forEach(g=>{const d=document.createElement('div');d.className='grp';
  d.innerHTML=`<span>${esc(g.g)}</span><span class="n">${g.n}</span>`;
  d.onclick=()=>openGroup(g.g); L.appendChild(d);});
 if(!gs.length)L.innerHTML='<div class="muted" style="padding:14px">그룹 없음</div>';
}
async function showGroups(){loadGroups();}
async function openGroup(g){
 const r=await fetch('/api/group?g='+encodeURIComponent(g)); hits=await r.json();
 $('backBtn').style.display='';
 renderHits();
}
function renderHits(){
 const L=$('list'); L.innerHTML='';
 if(!hits.length){L.innerHTML='<div class="muted" style="padding:14px">항목 없음</div>';return;}
 hits.forEach((h,i)=>{
  const d=document.createElement('div'); d.className='hit'; d.onclick=()=>select(i,d);
  d.innerHTML=`<div class="key">${h.key}${h.budget?` · 예산 ${h.budget}B`:''} · ${h.src}</div>
    <div class="jp">${esc(h.jp)}</div><div class="kr">${esc(h.kr)||'<span class=muted>(빈칸)</span>'}</div>`;
  L.appendChild(d);
 });
}
async function search(){
  const q=$('q').value.trim(); if(!q)return;
  const r=await fetch('/api/search?q='+encodeURIComponent(q)); hits=await r.json();
  $('backBtn').style.display='none';
  renderHits();
}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function select(i,el){
  document.querySelectorAll('.hit.sel').forEach(x=>x.classList.remove('sel'));
  el.classList.add('sel'); cur=i; const h=hits[i];
  $('panel').innerHTML=`
   <div class="meta">${h.key} · ${h.src}${h.budget?` · 예산 <b>${h.budget}B</b>`:''}</div>
   <div class="jp">${esc(h.jp)}</div>
   <div class="meta">새 번역 (개행은 실제 줄바꿈으로):</div>
   <textarea id="kr">${esc(h.kr)}</textarea>
   <div id="vres"></div>
   <button onclick="check()">검사</button>
   <button onclick="save()">저장</button>
   <div id="log"></div>`;
  $('kr').addEventListener('input',debounce(check,500));
}
let t=null; function debounce(f,ms){return()=>{clearTimeout(t);t=setTimeout(f,ms);};}
async function check(){
  if(cur===null)return;
  const r=await fetch('/api/check',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({i:hits[cur].i,kr:$('kr').value})});
  const v=await r.json(); showV(v); return v;
}
function showV(v){
  $('vres').innerHTML=v.errs.map(e=>`<div class="err">[거부] ${esc(e)}</div>`).join('')
    +v.warns.map(w=>`<div class="warn">[주의] ${esc(w)}</div>`).join('')
    +(!v.errs.length?'<div class="ok">[OK] 제약 통과</div>':'');
}
async function save(){
  if(cur===null)return;
  const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({i:hits[cur].i,kr:$('kr').value})});
  const v=await r.json(); showV(v);
  if(v.saved){hits[cur].kr=$('kr').value; $('log').textContent='[저장] '+hits[cur].key+' (적용 대기)'; pending();}
}
async function pending(){
  const r=await fetch('/api/pending'); const p=await r.json();
  $('pend').textContent=p.total?`대기 ${p.total}건 (${p.desc})`:'';
  $('applyBtn').textContent=p.total?'적용+롬배치':'롬배치 재시도';
}
async function applyAll(){
  $('applyBtn').disabled=true; $('applyBtn').textContent='적용 중...';
  const r=await fetch('/api/apply',{method:'POST'}); const v=await r.json();
  $('applyBtn').disabled=false;
  const lg=$('log')||$('panel'); (lg.id==='log'?lg:lg).textContent=v.log.join('\\n');
  if($('log'))$('log').textContent=v.log.join('\\n'); else alert(v.log.join('\\n'));
  pending();
}
pending();
</script></body></html>"""


def _hits(q):
    out = []
    alt = E.garbled_alt(q)
    with LOCK:
        for i, s in enumerate(S):
            r = s["ref"]
            if (q in (r.get("kr") or "") or q in (r.get("jp") or "")
                    or (alt and alt in (r.get("jp") or ""))):
                out.append({"i": i, "key": s["key"], "src": s["src"],
                            "jp": r.get("jp") or "", "kr": r.get("kr") or "",
                            "budget": s["budget"]})
                if len(out) >= 50:
                    break
    return out


def _mark_dirty(s):
    if s["src"] == "scene":
        DIRTY["scenes"].add(s["scene"])
    elif s["src"] == "skit":
        DIRTY["skit"].add(s["scene"])
    elif s["src"] == "slot2":
        DIRTY["rows"].append(("slot2", s["ref"]))
    elif s["src"] == "menu":
        DIRTY["rows"].append(("menu", s["ref"]))
    elif s["src"] == "bb":
        DIRTY["rows"].append(("bb", s["ref"]))
    else:
        DIRTY["rows"].append(("eboot", s["ref"]))


def _pending():
    n = len(DIRTY["scenes"]) + len(DIRTY["rows"]) + (1 if DIRTY["slot2"] else 0)
    desc = []
    if DIRTY["scenes"]:
        desc.append("씬 " + ",".join(map(str, sorted(DIRTY["scenes"]))))
    if DIRTY["rows"]:
        desc.append(f"제자리 {len(DIRTY['rows'])}")
    if DIRTY["slot2"]:
        desc.append("슬롯2")
    if DIRTY["skit"]:
        desc.append(f"스킷 {len(DIRTY['skit'])}(별도빌드)")
    return {"total": n, "desc": " / ".join(desc)}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            b = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/search":
            q = urllib.parse.parse_qs(u.query).get("q", [""])[0]
            self._json(_hits(q))
        elif u.path == "/api/pending":
            self._json(_pending())
        elif u.path == "/api/groups":
            q = urllib.parse.parse_qs(u.query).get("q", [""])[0]
            out = [{"g": g, "n": len(GROUPS[g])} for g in GLIST if q in g]
            self._json(out[:400])
        elif u.path == "/api/group":
            g = urllib.parse.parse_qs(u.query).get("g", [""])[0]
            idxs = GROUPS.get(g, [])
            out = []
            with LOCK:
                for i in idxs[:600]:
                    x = S[i]; r = x["ref"]
                    out.append({"i": i, "key": x["key"], "src": x["src"],
                                "jp": r.get("jp") or "", "kr": r.get("kr") or "",
                                "budget": x["budget"]})
            self._json(out)
        else:
            self._json({"err": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/check":
            s = S[int(body["i"])]
            errs, warns = E.validate(s["ref"].get("jp") or "", body.get("kr", ""), s["budget"])
            self._json({"errs": errs, "warns": warns})
        elif self.path == "/api/save":
            with LOCK:
                s = S[int(body["i"])]
                kr = body.get("kr", "")
                errs, warns = E.validate(s["ref"].get("jp") or "", kr, s["budget"])
                if errs:
                    self._json({"errs": errs, "warns": warns, "saved": False})
                    return
                E.save_edit(s, kr)
                _mark_dirty(s)
            self._json({"errs": [], "warns": warns, "saved": True})
        elif self.path == "/api/apply":
            log = []
            with LOCK:
                for sc in sorted(DIRTY["scenes"]):
                    try:
                        log.append(E.apply_scene(sc))
                    except Exception as ex:
                        log.append(f"[오류] 씬{sc}: {ex}")
                for kind, ref in DIRTY["rows"]:
                    try:
                        if kind == "eboot":
                            log.append(E.apply_eboot_row(ref))
                        elif kind == "menu":
                            log.append(E.apply_menu_row(ref))
                        elif kind == "bb":
                            log.append(E.apply_bb_row(ref))
                        elif kind == "slot2":
                            log.append(E.apply_slot2_row(ref))
                    except Exception as ex:
                        log.append(f"[오류] {kind}@{ref.get('off') or ref.get('roff')}: {ex}")
                if DIRTY["skit"]:
                    log.append(f"[안내] 스킷 {sorted(DIRTY['skit'])} 저장됨 - 적용은 스킷 전체 재빌드 필요")
                DIRTY["scenes"].clear(); DIRTY["rows"].clear(); DIRTY["slot2"] = False
                log.append(E.deploy())
            self._json({"log": log})
        else:
            self._json({"err": "not found"}, 404)


def main():
    port = 8787
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://localhost:{port}"
    print(f"[OK] ToR translation editor: {url}  (Ctrl+C = stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[bye]")


if __name__ == "__main__":
    main()
