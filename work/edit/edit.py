# -*- coding: utf-8 -*-
# 통합 번역 편집 툴 (2026-07-25)
#  화면에서 이상한 번역을 발견 -> 검색 -> 수정 -> 제약 자동검증 -> 올바른 경로로 적용+롬배치.
#
#  사용: py work\edit\edit.py
#   검색> (한글/일본어 아무거나 입력)     - 전 소스 검색
#   번호 입력 -> 새 번역 입력 -> 자동 검증(태그/바이트예산/글리프) -> 저장
#   a = 대기 중인 수정 전부 적용(씬 재빌드/EBOOT 제자리/슬롯2 재압축) + 롬 배치
#   q = 종료
#
#  소스별 적용 경로:
#   scene  translation/*.json      -> orddup+pin 단일씬 재빌드 (선택지/필드라벨 보존, 검증됨)
#   eboot  eboot_work/item_work    -> 제자리 kr+공백(jplen 한정, 태그클러스터 끝 보존)
#   menu   menu_work (슬롯3960)    -> 위와 동일 규칙 (널 잠식 금지)
#   slot2  slot2_work              -> work/battle_jp/_patch.py 호출(전체 재압축, 오버레이 보존)
#   skit   work/skit_jp/skits/*    -> 저장만 (적용은 스킷 전체 재빌드 필요 - 안내 출력)
#
#  제약 규칙(자동 강제):
#   - 태그(<...>) 시퀀스는 jp 와 동일해야 함 (색짝/개행/치환 보존)
#   - eboot/menu/slot2: len(enc(kr)) <= len(enc(jp)) (jplen 초과 = 널 잠식 -> 거부)
#   - 글리프: tbl_full_kr 에 없는 문자 거부(회수폰트에 없음 = 깨짐)
#   - 6점말줄임/……  경고 (3점 … 권장)
import glob
import json
import os
import re
import struct
import subprocess
import sys

os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib"); sys.path.insert(0, ".")

TKR = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
TALL = json.load(open("tbl_all.json", encoding="utf-8"))["TBL"]
INV = {v: k.upper() for k, v in TKR.items()}          # kr 인코딩용 (회수폰트)
INVA = {v: k.upper() for k, v in TALL.items()}        # jp 원문 인코딩용 (원본 테이블)
JPMAP = {**INV, **INVA}                               # jp: 원본 우선(코드 겹치면 tbl_all 승)
TAG = re.compile(r"<[^<>]+>")


def enc_full(s, table):
    """태그(<XX>/<XXXX>)+텍스트 -> 바이트. table = JPMAP(원문) 또는 INV(한글)."""
    o = bytearray(); i = 0
    while i < len(s):
        m = TAG.match(s, i)
        if m:
            t = m.group(0)[1:-1]
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                o.append(int(t, 16))
            elif re.fullmatch(r"[0-9A-Fa-f]{4}", t):
                o.extend(int(t, 16).to_bytes(2, "big"))
            else:
                raise ValueError("named tag: " + t)
            i = m.end(); continue
        c = s[i]
        if c == " ":
            o.append(0x20)
        elif 0x20 < ord(c) < 0x7F:
            o.append(ord(c))
        else:
            o.extend(bytes.fromhex(table[c]))
        i += 1
    return bytes(o)
ROM = r"C:\Users\home\Desktop\프로그램\ppsspp_win\roms\torj\PSP_GAME"
PINS_PATH = "work/edit/pins.json"          # 씬별 미참조 라벨 pin {scene:{rel:kr}}
LOG_PATH = "work/edit/edit_log.jsonl"


def enc_len(s, jp=False):
    """eboot류 바이트 길이: <XX>=1B <XXXX>=2B ASCII=1B 나머지=2B. 인코딩 불가 문자는 예외."""
    n = 0
    i = 0
    while i < len(s):
        m = TAG.match(s, i)
        if m:
            t = m.group(0)[1:-1]
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                n += 1
            elif re.fullmatch(r"[0-9A-Fa-f]{4}", t):
                n += 2
            else:
                n += 2      # 이름태그 등 - 대략치(씬/스킷은 빌드에서 정밀 검증)
            i = m.end()
            continue
        c = s[i]
        if c == " " or (0x20 <= ord(c) < 0x7F):
            n += 1
        else:
            if c not in (JPMAP if jp else INV):
                raise KeyError(c)
            n += 2
        i += 1
    return n


def garbled_alt(q):
    """깨진 한글 역산: 화면의 깨진 글자(회수폰트) -> 원래 한자 검색어.
    예: '쭙캤' -> '隊長'. 바뀐 글자가 있으면 대체 검색어 반환, 없으면 None."""
    ch = []
    changed = False
    _tall = {k.upper(): v for k, v in TALL.items()}
    for c in q:
        code = INV.get(c)
        orig = _tall.get(code) if code else None
        if orig and orig != c:
            ch.append(orig); changed = True
        else:
            ch.append(c)
    return "".join(ch) if changed else None


def missing_glyphs(s):
    out = set()
    i = 0
    while i < len(s):
        m = TAG.match(s, i)
        if m:
            i = m.end(); continue
        c = s[i]
        if not (c == " " or 0x20 <= ord(c) < 0x7F or c in INV or c == "\n"):
            out.add(c)
        i += 1
    return out


def validate(jp, kr, budget=None):
    """(오류목록, 경고목록)"""
    errs, warns = [], []
    tj, tk = TAG.findall(jp), TAG.findall(kr)
    if tj != tk:
        errs.append(f"태그 불일치: jp{tj} != kr{tk}")
    mg = missing_glyphs(kr)
    if mg:
        errs.append("폰트에 없는 문자: " + " ".join(sorted(mg)))
    if budget is not None and not errs:
        try:
            L = enc_len(kr)
            if L > budget:
                errs.append(f"바이트 초과: {L}B > 예산 {budget}B (축약 필요)")
            else:
                warns.append(f"길이 {L}B / 예산 {budget}B")
        except KeyError as e:
            errs.append(f"인코딩 불가 문자: {e}")
    if "……" in kr or "‥" in kr:
        warns.append("말줄임은 3점 … 하나만 권장")
    return errs, warns


# ---------- 소스 로드 ----------
def load_sources():
    S = []
    for f in sorted(glob.glob("translation/*.json")):
        sc = int(os.path.basename(f)[:-5])
        d = json.load(open(f, encoding="utf-8"))
        for ln in d.get("lines", []):
            S.append({"src": "scene", "file": f, "scene": sc, "ref": ln,
                      "key": f"씬{sc}#{ln.get('id')}", "budget": None})
    for f, tag in [("work/eboot_jp/eboot_work.json", "eboot"),
                   ("work/item_jp/item_work.json", "eboot"),
                   ("work/menu_jp/menu_work.json", "menu"),
                   ("work/battle_jp/slot2_work.json", "slot2")]:
        rows = json.load(open(f, encoding="utf-8"))
        for r in rows:
            try:
                budget = enc_len(r["jp"], jp=True)       # jplen = 안전 예산
            except KeyError:
                budget = int(r.get("avail", 0)) or None
            # ★eboot_work(스킷제목/네비/이름/메뉴 등)는 널채움 검증 카테고리(_patch.py) -
            #  원 패처가 avail 기준으로 넣어 kr이 jplen 초과인 행 존재(は今…」 10B vs
            #  는 지금…」 11B, avail 13). avail-1(종단널 1개 보존)까지 허용 (2026-08-03).
            #  콘텐츠 계열(cbatch/dbatch)은 널구조 민감이라 jplen 유지.
            if f == "work/eboot_jp/eboot_work.json" and budget:
                av = int(r.get("avail", 0))
                if av - 1 > budget:
                    budget = av - 1
            S.append({"src": tag, "file": f, "ref": r,
                      "key": f"{tag}@{r.get('off') or r.get('roff')}", "budget": budget})
    for f in sorted(glob.glob("work/skit_jp/skits/*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for ln in d.get("lines", []):
            S.append({"src": "skit", "file": f, "scene": d.get("slot"), "ref": ln,
                      "key": f"스킷{d.get('slot')}#{ln.get('id')}", "budget": None})
    # cbatch/dbatch/tbatch: 본문+_kr 쌍 (tbatch = 스킷제목/네비 「」형 - 2026-08-03 편입)
    for main in sorted(glob.glob("work/eboot_jp/cbatch_*.json") + glob.glob("work/eboot_jp/dbatch_*.json")
                       + glob.glob("work/eboot_jp/tbatch_*.json")):
        if main.endswith("_kr.json"):
            continue
        krf = main[:-5] + "_kr.json"
        if not os.path.exists(krf):
            continue
        md = json.load(open(main, encoding="utf-8"))
        kd = json.load(open(krf, encoding="utf-8"))
        km = {r["off"]: r.get("kr", "") for r in kd}
        for ln in md.get("lines", []):
            off = ln["off"]
            ref = {"off": off, "jp": ln["jp"], "kr": km.get(off, "")}
            try:
                budget = enc_len(ref["jp"], jp=True)
            except KeyError:
                budget = int(ln.get("avail", 0)) or None
            S.append({"src": "eboot", "file": krf, "pair": True, "ref": ref,
                      "key": f"eboot@{off}", "budget": budget})
    # rbatch (잔여 EBOOT)
    for f in sorted(glob.glob("work/eboot_jp/rbatch/*.json")):
        for r in json.load(open(f, encoding="utf-8")):
            if not r.get("kr"):
                continue
            try:
                budget = enc_len(r["jp"], jp=True)
            except KeyError:
                budget = int(r.get("len", 0)) or None
            S.append({"src": "eboot", "file": f, "ref": r,
                      "key": f"eboot@{r['off']}", "budget": budget})
    # battle help
    f = "work/battle/eboot_bh.json"
    if os.path.exists(f):
        for r in json.load(open(f, encoding="utf-8")):
            if not r.get("kr"):
                continue
            try:
                budget = enc_len(r["jp"], jp=True)
            except KeyError:
                budget = int(r.get("avail", 0)) or None
            S.append({"src": "eboot", "file": f, "ref": r,
                      "key": f"eboot@{r['off']}", "budget": budget})
    # 배틀북 (슬롯16185 + 슬롯2사본 이중적용)
    for f in sorted(glob.glob("work/battle_jp/bb_batch/*.json")):
        for r in json.load(open(f, encoding="utf-8")):
            if not r.get("kr"):
                continue
            try:
                budget = enc_len(r["jp"], jp=True)
            except KeyError:
                budget = int(r.get("len", 0)) or None
            S.append({"src": "bb", "file": f, "ref": r,
                      "key": f"배틀북@{r['off']:#x}" if isinstance(r["off"], int) else f"배틀북@{r['off']}",
                      "budget": budget})
    return S


# ---------- 적용기 ----------
# 특수 씬 = 전용 재빌드 도구 위임 (일반 orddup 로 재빌드하면 pin/시스템복원 소실!)
SPECIAL_SCENES = {
    4278: ["work/speakers_jp/_pin_scene.py"],   # 술집 미니게임 pin + 이름판 pin
    4281: ["work/speakers_jp/_pin_scene.py"],   # 식당 이름판 pin
    4274: ["work/speakers_jp/_sysrestore.py"],  # 여관 시스템 문자열 복원 + pin
    4307: ["work/speakers_jp/_sysrestore.py"],  # 페트나잔카 여관 시스템 복원 + pin
    4341: ["work/speakers_jp/_sysrestore.py"],  # 새니타운 여관 시스템 복원 + pin
    4389: ["work/speakers_jp/_sysrestore.py"],  # 아니카말 여관 시스템 복원 + pin
    4452: ["work/speakers_jp/_sysrestore.py"],  # 여관 시스템 복원 + pin
    4622: ["work/speakers_jp/_sysrestore.py"],  # 여관 시스템 복원 + pin
    4918: ["work/speakers_jp/_sysrestore.py"],  # 여관 시스템 복원 + pin
    4198: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5155: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5156: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5157: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5158: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5159: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5160: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5161: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    5162: ["work/speakers_jp/_sysrestore.py"],  # 식재조달시설(매지컬포트) 전체 pin
    4475: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4539: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4579: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4590: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4609: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4642: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4708: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    4265: ["work/speakers_jp/_sysrestore.py"],  # 여관/식재점 시스템 복원 + pin
    # ★2026-08-02 전수 서수감사(미참조 탈락/표류삽입 99씬)로 sysrestore 편입 -
    #  select/notice 서수 JP 완전일치 검증됨. 이후 재빌드도 반드시 _sysrestore 경로.
    **{sc: ["work/speakers_jp/_sysrestore.py"] for sc in (
        4201, 4217, 4259, 4268, 4282, 4288, 4289, 4363, 4365, 4410, 4420, 4433,
        4499, 4500, 4542, 4543, 4545, 4565, 4574, 4585, 4589, 4591, 4592, 4597,
        4600, 4606, 4624, 4630, 4636, 4647, 4654, 4661, 4673, 4676, 4684, 4685,
        4686, 4687, 4688, 4689, 4690, 4691, 4692, 4693, 4694, 4695, 4701, 4707,
        4725, 4743, 4749, 4762, 4776, 4792, 4820, 4851, 4895, 4916, 4917, 5010,
        5029, 5035, 5036, 5037, 5038, 5040, 5042, 5043, 5044, 5045, 5046, 5047,
        5048, 5049, 5050, 5051, 5052, 5053, 5054, 5056, 5057, 5060, 5062, 5067,
        5068, 5075, 5077, 5081, 5082, 5085, 5088, 5092, 5096, 5108, 5109, 5115,
        5167, 5178, 5179)},
    4762: ["work/speakers_jp/_sysrestore.py"],  # 문 조사 메시지 PINALL(참조 문자열 고정 오프셋 판독)
    5167: ["work/speakers_jp/_fix5167_ika.py"],  # 음식나눔 pin + イカ->오징어 재배치 (내부에서 _sysrestore 선행)
    # 가나 자유입력 퀴즈 씬: 비교어/프롬프트/에코 블록 PINALL (2026-08-04)
    4252: ["work/speakers_jp/_sysrestore.py"],
    4448: ["work/speakers_jp/_sysrestore.py"],
    4563: ["work/speakers_jp/_sysrestore.py"],
    # 스테일 이름/라벨 오퍼랜드 보유 씬 (2026-08-04 전수감사 - _sysrestore OP갱신 패스 필요)
    4269: ["work/speakers_jp/_sysrestore.py"],
    4319: ["work/speakers_jp/_sysrestore.py"],
    4586: ["work/speakers_jp/_sysrestore.py"],
    4747: ["work/speakers_jp/_sysrestore.py"],
}


def apply_scene(sc):
    """orddup+pin 단일씬 재빌드 -> DAT_jp_final 제자리."""
    if sc in SPECIAL_SCENES:
        import subprocess
        env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run(["py", SPECIAL_SCENES[sc][0], str(sc)],
                           capture_output=True, text=True, encoding="utf-8",
                           cwd=r"D:\clean_project", env=env)
        out = (r.stdout or "") + (r.stderr or "")
        if "[OK]" in out and "[SAVED]" in out:
            return f"[OK] 씬{sc} (전용 도구 재빌드)"
        return f"[실패] 씬{sc} 전용 도구: {out[-200:]}"
    from pathlib import Path
    from lxml import etree
    from pythonlib.formats.rebirth.scpk import Scpk
    from pythonlib.formats.rebirth.theirsce import Theirsce
    from pythonlib.utils import comptolib
    from story_pipeline_bin import make_mini
    from build_scene import inject_translation
    from build_all_jp import swap_theirsce, parse_blobs
    inv2 = {v: k for k, v in TKR.items()}

    def enc(s):
        o = bytearray()
        for c in s:
            o.append(0x20) if c == " " else o.extend(bytes.fromhex(inv2[c].upper() if False else inv2[c]))
        return bytes(o)

    PTR = 0x126F90
    def rp(buf, ds):
        p = []; k = 0
        while True:
            v = struct.unpack_from("<I", buf, PTR + k * 4)[0]
            if k > 0 and (v < p[-1] or v > ds * 1.05):
                break
            p.append(v); k += 1
            if k > 40000:
                break
        return p

    pins = {}
    if os.path.exists(PINS_PATH):
        pins = {int(k): {int(r): v for r, v in vv.items()}
                for k, vv in json.load(open(PINS_PATH, encoding="utf-8")).items()}
    ex = pins.get(sc, {})

    src = open("DAT.BIN", "rb").read()
    sp = rp(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    dp = rp(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    p0 = sp[sc]; base = src.rfind(b"SCPK", max(0, p0 - 64), p0 + 8)
    nf = struct.unpack_from("<I", src, base + 8)[0]
    sizes = [struct.unpack_from("<I", src, base + 16 + 4 * k)[0] for k in range(nf)]
    scont = bytes(src[base:base + 16 + 4 * nf + sum(sizes)])
    Path("work/_ed.bin").write_bytes(scont)
    scpk = Scpk.from_path(Path("work/_ed.bin")); orig = scpk.rsce
    so = Theirsce(orig).strings_offset
    mini_ex = make_mini("tbl_all.json"); mini_ex.id = 1
    Path("work/_ed.xml").write_bytes(mini_ex.get_xml_from_theirsce(Theirsce(orig), "Story"))
    d = json.load(open(f"translation/{sc}.json", encoding="utf-8"))
    inject_translation("work/_ed.xml", "work/_edk.xml", d.get("lines", []))
    NM = json.load(open("work/names_npc.json", encoding="utf-8"))
    tree = etree.parse("work/_edk.xml"); root = tree.getroot()
    for e in root.findall(".//Speakers/Entry"):
        jt = e.find("JapaneseText"); et = e.find("EnglishText")
        if jt is not None and et is not None and (jt.text or "") in NM:
            et.text = NM[jt.text]
    mini_in = make_mini("tbl_full_kr.json"); mini_in.id = 1
    ents = [e for e in root.iter("Entry")
            if e.find("Id") is not None and e.find("Id").text != "-1"
            and e.find("PointerOffset") is not None
            and e.find("PointerOffset").text not in (None, "-1")]
    groups = {}
    normset = set()                                  # 정규화 위치 = pin 중복 방지 전용
    for e in ents:
        for x in e.find("PointerOffset").text.split(","):
            p = int(x)
            o = struct.unpack_from("<H", orig, p)[0]
            # ★그룹 키 = 원시 오프셋 (_patch_all 검증 동작과 동일 - 서수 보존).
            #   정규화를 그룹 키에 쓰면 ptr=0(빈문자열 관용)과 다른 엔트리가 병합돼
            #   문자열 수가 줄어 선택지 서수가 깨짐 (2026-07-25 미나르 상점 사고).
            groups.setdefault(o, [e, []])[1].append(p)
            o2 = o
            while so + o2 < len(orig) and orig[so + o2] == 0:
                o2 += 1
            normset.add(o2)
    # ★XML 미포착 이름 오퍼랜드 (48 20 04 f8 + u16 풀오프셋, 2026-07-30 일반해):
    #  이름판 등의 이름 참조. 일반 포인터처럼 갱신, 미참조 타깃은 names_npc 로 삽입.
    _jptbl = {k.lower(): v for k, v in json.load(open("tbl_all.json", encoding="utf-8"))["TBL"].items()}
    _known = {pp for _, (ee, pps) in groups.items() for pp in pps}
    _q = 0
    while True:
        _q = orig.find(b"\x48\x20\x04\xf8", _q, so - 6)
        if _q < 0:
            break
        _p = _q + 4
        _v = struct.unpack_from("<H", orig, _p)[0]
        _ok = so + _v < len(orig) and orig[so + _v] != 0 and (_v == 0 or orig[so + _v - 1] == 0)
        if _p not in _known and _ok:
            if _v in groups:
                groups[_v][1].append(_p)
            else:
                _st = so + _v; _n = _st
                while _n < len(orig) and orig[_n] != 0:
                    _n += 1
                _jpname = ""
                _i2 = _st
                while _i2 < _n:
                    if orig[_i2] < 0x80:
                        _jpname += chr(orig[_i2]); _i2 += 1
                        continue
                    _ch = _jptbl.get(orig[_i2:_i2 + 2].hex().lower())
                    if _ch is None:
                        _jpname = None; break
                    _jpname += _ch; _i2 += 2
                _nm = json.load(open("work/names_npc.json", encoding="utf-8")) if not hasattr(apply_scene, "_nm") else apply_scene._nm
                apply_scene._nm = _nm
                _kr = _nm.get(_jpname or "")
                _kb = enc(_kr) if _kr else bytes(orig[_st:_n])
                groups[_v] = [("RAW", _kb), [_p]]
        _q += 1
    allstarts = []
    q = so
    while q < len(orig):
        if orig[q] == 0:
            q += 1; continue
        allstarts.append(q - so)
        while q < len(orig) and orig[q] != 0:
            q += 1
    unref = [o for o in allstarts if o not in groups and o not in normset and o in ex]
    items = sorted(set(list(groups.keys()) + unref))
    out = bytearray(orig[:so + 1]); newoff = {}; overshoot = 0
    for o in items:
        if o in groups:
            e, _ = groups[o]
            if isinstance(e, tuple) and e[0] == "RAW":
                b = e[1]
            else:
                try:
                    b = mini_in.get_node_bytes(e)
                except Exception:
                    b = b""
            newoff[o] = len(out) - so
            out += b + b"\x00"
        else:
            cur = len(out) - so
            if cur > o:
                overshoot += 1
            else:
                out += b"\x00" * (o - cur)
            st = so + o; n = st
            while n < len(orig) and orig[n] != 0:
                n += 1
            ob = orig[st:n]
            kb = enc(ex[o])
            assert len(kb) <= len(ob), (o, ex[o])
            newoff[o] = len(out) - so
            out += kb + b"\x00"
    for o, (e, ptrs) in groups.items():
        for p in ptrs:
            struct.pack_into("<H", out, p, newoff[o])
    new = bytes(out)
    assert new.count(b"select") == orig.count(b"select")
    if overshoot:
        return f"[실패] 씬{sc}: pin 오버슛 {overshoot}"
    # ★제자리 블롭 교체 (2026-07-29): 컨테이너 재조립 금지!
    #   재조립은 블롭이 커지면 뒤 꼬리(SCPK 서브컨테이너 등)를 슬롯 밖으로 밀어 파괴함
    #   (4273 선택지 깨짐의 진범 - 4273_깨짐_원인확인.md 체크리스트로 규명).
    #   방식: 클린 원본 컨테이너의 블롭 슬롯(크기테이블 값) 안에 새 블롭 + '#' 패딩.
    #   크기테이블/꼬리/컨테이너 길이 완전 불변. greedy -> 최적파스 캐스케이드.
    ct = scpk._rsce_comp_type
    blobs = parse_blobs(scont)
    _, off, size, idx = next(bb for bb in blobs if bb[0] == "sce")
    slot = size                                   # 원본 블롭 슬롯(정렬패딩 포함)
    blob = comptolib.compress_data(new, version=ct)
    how = "greedy"
    if len(blob) > slot:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("sp", "work/synopsis_jp/_spaced_inplace.py")
        mod = ilu.module_from_spec(spec); spec.loader.exec_module(mod)
        init = open("work/synopsis_jp/lzss_init.bin", "rb").read()
        body = mod.lzss_encode_optimal(new, init)
        blob = struct.pack("<b", 1) + struct.pack("<L", len(body)) + struct.pack("<L", len(new)) + body
        assert comptolib.decompress_data(blob) == new
        how = "optimal"
    if len(blob) > slot:
        return f"[실패] 씬{sc}: 블롭 {len(blob)-slot}B 초과 (원본슬롯 {slot}B)"
    newc = bytes(scont[:off]) + blob + b"#" * (slot - len(blob)) + bytes(scont[off + size:])
    assert len(newc) == len(scont)
    q0 = dp[sc]; b2 = dat.rfind(b"SCPK", max(0, q0 - 64), q0 + 8)
    assert bytes(dat[b2:b2 + 4]) == b"SCPK"
    dat[b2:b2 + len(newc)] = newc
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    return f"[OK] 씬{sc} 재빌드 (블롭 {len(blob)}/{slot}B, {how}, 꼬리보존)"


def apply_eboot_row(r):
    """제자리 kr+공백(jplen 한정). 태그클러스터가 끝이면 공백은 그 앞.
    ★avail 보유 행(eboot_work = 널채움 검증 카테고리)은 avail-1 까지 허용 -
    초과분은 원 패처와 동일하게 널채움 기록 (2026-08-03, 스킷제목 は今…」 실증)."""
    off = int(r.get("off") or 0)
    jb = enc_full(r["jp"], JPMAP); kb = enc_full(r["kr"], INV)
    av = int(r.get("avail", 0))
    if len(kb) > len(jb) and av and len(kb) <= av - 1:
        eb = bytearray(open("EBOOT_jp_new.BIN", "rb").read())
        eb[off:off + av] = kb + b"\x00" * (av - len(kb))
        open("EBOOT_jp_new.BIN", "wb").write(bytes(eb))
        return f"[OK] eboot@{off} ({len(kb)}B/avail {av}B 널채움)"
    if len(kb) > len(jb):
        return f"[실패] eboot@{off}: {len(kb)}B > jplen {len(jb)}B"
    # 끝 태그클러스터(제어바이트 연속) 분리 -> [본문][공백][클러스터]
    CL = {0x01, 0x05, 0x06, 0x0B, 0x0D, 0x04}
    ci = len(kb)
    while ci > 0 and kb[ci - 1] in CL:
        ci -= 1
    body, cluster = kb[:ci], kb[ci:]
    new = body + b" " * (len(jb) - len(kb)) + cluster
    eb = bytearray(open("EBOOT_jp_new.BIN", "rb").read())
    eb[off:off + len(jb)] = new
    open("EBOOT_jp_new.BIN", "wb").write(bytes(eb))
    return f"[OK] eboot@{off} ({len(kb)}B/{len(jb)}B)"


def apply_menu_row(r):
    """슬롯3960 roff 제자리. eboot 와 동일 규칙 + 슬롯 위치는 EBOOT ptr[3960]."""
    eb = open("EBOOT_jp_new.BIN", "rb").read()
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    p = []; k = 0
    while True:
        v = struct.unpack_from("<I", eb, 0x126F90 + k * 4)[0]
        if k > 0 and (v < p[-1] or v > len(dat) * 1.05):
            break
        p.append(v); k += 1
        if k > 40000:
            break
    bk = p[3960]
    roff = int(r["roff"])
    jb = enc_full(r["jp"], JPMAP); kb = enc_full(r["kr"], INV)
    if len(kb) > len(jb):
        return f"[실패] menu@{roff:#x}: {len(kb)}B > jplen {len(jb)}B"
    CL = {0x01, 0x05, 0x06, 0x0B, 0x0D, 0x04, 0xC0, 0xE0}
    ci = len(kb)
    while ci > 0 and kb[ci - 1] in CL:
        ci -= 1
    body, cluster = kb[:ci], kb[ci:]
    new = body + b" " * (len(jb) - len(kb)) + cluster
    dat[bk + roff:bk + roff + len(jb)] = new
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    return f"[OK] menu(3960)@{roff:#x} ({len(kb)}B/{len(jb)}B)"


def apply_slot2_row(r):
    """슬롯2 단일 행 제자리: 스트림1 해제 -> off 에 kr+공백(jplen) -> 재압축(<=310976, 오버레이 보존).
    (_patch.py 전체 재빌드는 바이너리 레이아웃 수정을 되돌리므로 사용 금지 - CLAUDE.md)"""
    import importlib
    sys.path.insert(0, r"D:\PythonLib")
    from pythonlib.utils import comptolib
    eb = open("EBOOT_jp_new.BIN", "rb").read()
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    p = []; k = 0
    while True:
        v = struct.unpack_from("<I", eb, 0x126F90 + k * 4)[0]
        if k > 0 and (v < p[-1] or v > len(dat) * 1.05):
            break
        p.append(v); k += 1
        if k > 40000:
            break
    b2 = p[2]; t = dat[b2]
    cs = struct.unpack_from("<I", dat, b2 + 1)[0]
    s1 = bytearray(comptolib.decompress_data(bytes(dat[b2:b2 + 9 + cs])))
    off = int(r["off"])
    kb = enc_full(r["kr"], INV)
    # ★내용 검색 기반 (정렬기가 조각 위치를 옮기므로 off 직접 사용 금지):
    #   이전 kr(있으면) 또는 jp 원문을 존에서 찾아 그 자리에 교체. 유일해야 함.
    LOZ, HIZ = 269585, 289236
    tgt = None
    prev = r.get("_prev")
    hist = []                                   # 편집로그의 모든 이력(최신 우선)
    if os.path.exists(LOG_PATH):
        for line in open(LOG_PATH, encoding="utf-8"):
            try:
                e2 = json.loads(line)
            except Exception:
                continue
            if e2.get("key") == f"slot2@{off}":
                for v in (e2.get("new"), e2.get("old")):
                    if v:
                        hist.append(v)
    hist.reverse()                              # 최신 항목 먼저
    cands = []
    srcs = [(prev, INV)] + [(h, INV) for h in hist] + [(r.get("jp"), JPMAP), (r.get("kr"), INV)]
    for cand_s, table in srcs:
        if not cand_s:
            continue
        try:
            cb = enc_full(cand_s, table)
        except Exception:
            continue
        cands.append(cb)
        cands.append(cb.rstrip(b""))       # 빌드 관례: 후행 <01> 체인 제거본
    seen = set()
    for cb in cands:
        if not cb or cb in seen:
            continue
        seen.add(cb)
        i1 = bytes(s1).find(cb, LOZ, HIZ)
        if i1 < 0:
            continue
        if bytes(s1).find(cb, i1 + 1, HIZ) >= 0:
            continue                            # 유일하지 않으면 다음 후보
        tgt = i1
        break
    if tgt is None:
        return f"[실패] slot2@{off}: 이전번역/원문을 스트림에서 못 찾음 (수동 확인 필요)"
    kb = kb.rstrip(b"")                    # 후행 <01> 제거(빌드 관례 유지)
    n = tgt
    while n < HIZ and s1[n] != 0:
        n += 1
    foot = n - tgt                              # 자기 발자국
    m = n
    while m < HIZ and s1[m] == 0:
        m += 1
    # ★확장(뒤 널 차용)은 다음 항목이 블록 꼬리(<04> 마커)일 때만 허용.
    #   색조각 체인 사이 구분널은 '개수'가 조립 기준이라 절대 잠식 금지 (왕의방패 사건).
    tail_ok = (m < HIZ and s1[m] == 4)
    ext = ((m - 1) - tgt) if tail_ok else foot
    if len(kb) > ext:
        lim = "블록꼬리한도" if tail_ok else "조각길이(체인 구분널 보호)"
        return f"[실패] slot2@{off}: {len(kb)}B > {ext}B ({lim} - 축약 필요 또는 수동)"
    if len(kb) <= foot:
        s1[tgt:n] = kb + b" " * (foot - len(kb))
    else:
        s1[tgt:tgt + len(kb)] = kb              # 블록꼬리널 차용(1개 보존)
    nb = comptolib.compress_data(bytes(s1), version=t)
    if len(nb) > 310976:
        return (f"[실패] slot2 재압축 {len(nb)}B > 310976 - LZ 민감성. "
                f"최소침습 패치 필요(수동): 해당 글자만 스왑 요청 바람")
    dat[b2:b2 + len(nb)] = nb
    for z in range(b2 + len(nb), b2 + 310976):
        dat[z] = 0xCD
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    return f"[OK] slot2@{off} ({len(kb)}B, 재압축 {len(nb)}B)"


def apply_bb_row(r):
    """배틀북: DAT 슬롯16185 + 슬롯2사본(+0xAF838) 이중 제자리 (jplen 한정)."""
    eb = open("EBOOT_jp_new.BIN", "rb").read()
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    p = []; k = 0
    while True:
        v = struct.unpack_from("<I", eb, 0x126F90 + k * 4)[0]
        if k > 0 and (v < p[-1] or v > len(dat) * 1.05):
            break
        p.append(v); k += 1
        if k > 40000:
            break
    roff = int(r["off"])
    jb = enc_full(r["jp"], JPMAP); kb = enc_full(r["kr"], INV)
    if len(kb) > len(jb):
        return f"[실패] 배틀북@{roff:#x}: {len(kb)}B > jplen {len(jb)}B"
    CL = {0x01, 0x05, 0x06, 0x0B, 0x0D, 0x04}
    ci = len(kb)
    while ci > 0 and kb[ci - 1] in CL:
        ci -= 1
    body, cluster = kb[:ci], kb[ci:]
    new = body + b" " * (len(jb) - len(kb)) + cluster
    for base in (p[16185], p[2] + 0xAF838):
        dat[base + roff:base + roff + len(jb)] = new
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    return f"[OK] 배틀북@{roff:#x} 이중적용 ({len(kb)}B/{len(jb)}B)"


def save_edit(h, new):
    """검증 통과한 새 번역을 소스 파일에 저장 + 로그. (검증은 호출측에서)"""
    r = h["ref"]
    old = r.get("kr", "")
    r["_prev"] = old
    r["kr"] = new
    if h["src"] in ("scene", "skit"):
        d = json.load(open(h["file"], encoding="utf-8"))
        for ln in d.get("lines", []):
            if str(ln.get("id")) == str(r.get("id")):
                ln["kr"] = new
        json.dump(d, open(h["file"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    elif h.get("pair"):
        rows = json.load(open(h["file"], encoding="utf-8"))
        found = False
        for rr in rows:
            if rr.get("off") == r.get("off"):
                rr["kr"] = new; found = True
        if not found:
            rows.append({"off": r["off"], "kr": new})
        json.dump(rows, open(h["file"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    else:
        rows = json.load(open(h["file"], encoding="utf-8"))
        keyf = "off" if "off" in r else "roff"
        for rr in rows:
            if rr.get(keyf) == r.get(keyf) and rr.get("jp") == r.get("jp"):
                rr["kr"] = new
        json.dump(rows, open(h["file"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(LOG_PATH, "a", encoding="utf-8") as lf:
        lf.write(json.dumps({"key": h["key"], "file": h["file"],
                             "old": old, "new": new}, ensure_ascii=False) + "\n")


def deploy():
    r = []
    for src_f, dst in [("DAT_jp_final.BIN", os.path.join(ROM, "USRDIR", "DAT.BIN")),
                       ("EBOOT_jp_new.BIN", os.path.join(ROM, "SYSDIR", "EBOOT.BIN"))]:
        try:
            import shutil
            shutil.copyfile(src_f, dst)
            r.append(f"[OK] {os.path.basename(dst)}")
        except PermissionError:
            r.append(f"[보류] {os.path.basename(dst)} - PPSSPP 종료 필요")
        except OSError as e:
            r.append(f"[보류] {os.path.basename(dst)} - {e}")
    return " / ".join(r)


# ---------- 메인 루프 ----------
def main():
    print("번역 편집 툴 - 검색어 입력 / 번호 선택 / a=적용 / q=종료")
    S = load_sources()
    print(f"(로드: 항목 {len(S)}개)")
    hits = []
    dirty_scenes = set(); dirty_rows = []; dirty_slot2 = False; dirty_skit = set()

    while True:
        try:
            cmd = input("\n검색/번호/a/q> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        if cmd == "q":
            if dirty_scenes or dirty_rows or dirty_slot2:
                print("! 적용 안 된 수정이 있습니다. a 로 적용하거나 그대로 q 재입력.")
                dirty_scenes2 = input("정말 종료? (y/q)> ").strip()
                if dirty_scenes2 not in ("y", "q"):
                    continue
            break
        if cmd == "a":
            for sc in sorted(dirty_scenes):
                print(" ", apply_scene(sc))
            for kind, ref in dirty_rows:
                if kind == "eboot":
                    print(" ", apply_eboot_row(ref))
                elif kind == "menu":
                    print(" ", apply_menu_row(ref))
                elif kind == "bb":
                    print(" ", apply_bb_row(ref))
                elif kind == "slot2":
                    print(" ", apply_slot2_row(ref))
            if dirty_slot2:
                print("  슬롯2 재압축 실행...")
                rr = subprocess.run([sys.executable, r"work\battle_jp\_patch.py"],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                print("  " + (rr.stdout or "").strip().splitlines()[-1] if rr.stdout else "  (출력없음)")
            if dirty_skit:
                print(f"  [안내] 스킷 {sorted(dirty_skit)} 저장됨 - 적용은 스킷 전체 재빌드 필요:")
                print("        py work\\skit_jp\\_build.py  (반드시 preskit 클린본 기반 - CLAUDE.md 참조)")
            dirty_scenes.clear(); dirty_rows.clear(); dirty_slot2 = False
            print(" ", deploy())
            continue
        if cmd.isdigit() and hits:
            k = int(cmd) - 1
            if not (0 <= k < len(hits)):
                print("범위 밖")
                continue
            h = hits[k]
            r = h["ref"]
            print(f"--- {h['key']} ({h['src']}) ---")
            print(f"JP: {r['jp']!r}")
            print(f"KR: {r.get('kr','')!r}")
            if h["budget"]:
                print(f"예산: {h['budget']}B (jp 기준)")
            new = input("새 번역 (빈칸=취소, 개행은 \\n)> ").rstrip("\n")
            if not new:
                print("(취소)")
                continue
            new = new.replace("\\n", "\n")     # \n 입력 -> 실제 개행
            errs, warns = validate(r["jp"], new, h["budget"])
            for w in warns:
                print("  [주의]", w)
            if errs:
                for er in errs:
                    print("  [거부]", er)
                continue
            save_edit(h, new)
            if h["src"] == "scene":
                dirty_scenes.add(h["scene"])
            elif h["src"] == "skit":
                dirty_skit.add(h["scene"])
            elif h["src"] == "slot2":
                dirty_rows.append(("slot2", r))
            elif h["src"] == "menu":
                dirty_rows.append(("menu", r))
            elif h["src"] == "bb":
                dirty_rows.append(("bb", r))
            else:
                dirty_rows.append(("eboot", r))
            print(f"[저장] {h['key']} (a 입력 시 적용)")
            continue
        # 검색
        qs = cmd
        alt = garbled_alt(qs)
        def _m(sr):
            r = sr["ref"]
            if qs in (r.get("kr") or "") or qs in (r.get("jp") or ""):
                return True
            return bool(alt) and (alt in (r.get("jp") or ""))
        hits = [s for s in S if _m(s)][:30]
        if alt and hits:
            print(f"(깨진글자 역산: {qs!r} -> {alt!r} 포함 검색)")
        if not hits:
            print("검색 결과 없음")
            continue
        for i, h in enumerate(hits, 1):
            r = h["ref"]
            kr = (r.get("kr") or "").replace("\n", "\\n")
            jp = (r.get("jp") or "").replace("\n", "\\n")
            b = f" [{h['budget']}B]" if h["budget"] else ""
            print(f"[{i:2}] {h['key']}{b}")
            print(f"     JP {jp[:44]}")
            print(f"     KR {kr[:44]}")
        if len(hits) == 30:
            print("(30개 초과 - 검색어를 더 구체적으로)")


if __name__ == "__main__":
    main()
