#!/usr/bin/env python3
# slot2_work.json(kr 채움)을 슬롯2 ELF에 제자리 패치 -> 재압축 -> DAT_jp_final in-place
#  - 인코딩: 한글/CJK=2B(tbl_full_kr), ASCII=1B, <XXXX>=2B값, <XX>=1B값
#  - 각 항목: 인코딩바이트+1(널) <= avail. 널종료+널패딩.
#  - 재압축이 원본 슬롯2 블롭(1061504B) 이내면 in-place (DAT 크기불변)
# 사용: py work\battle_jp\_patch.py [--check]   (--check = 검사만)
import json
import os
import re
import struct
import sys

os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
TAG4 = re.compile(r"<([0-9A-Fa-f]{4})>")
TAG2 = re.compile(r"<([0-9A-Fa-f]{2})>")


def enc(s):
    out = bytearray()
    i = 0
    while i < len(s):
        m = TAG4.match(s, i)
        if m:
            out += struct.pack(">H", int(m.group(1), 16))
            i = m.end()
            continue
        m = TAG2.match(s, i)
        if m:
            out += bytes([int(m.group(1), 16)])
            i = m.end()
            continue
        c = s[i]
        if c in inv:
            out += struct.pack(">H", inv[c])
            i += 1
            continue
        if ord(c) < 0x80:
            out += bytes([ord(c)])
            i += 1
            continue
        return None, c
    return bytes(out), None


check = "--check" in sys.argv
target = "DAT_jp_final.BIN"
for a in sys.argv[1:]:
    if a.startswith("--dat="):
        target = a.split("=", 1)[1]

# 원본 슬롯2 해제
PTR = 0x126F90
jp = open("DAT.BIN", "rb").read()
ebO = open("ULJS00132_EBOOT.BIN", "rb").read()
ptrs = []
i = 0
while True:
    v = struct.unpack_from("<I", ebO, PTR + i*4)[0]
    if i > 0 and (v < ptrs[-1] or v > len(jp)*1.05):
        break
    ptrs.append(v); i += 1
    if i > 40000:
        break
blob = jp[ptrs[2]:ptrs[3]]
csz = struct.unpack_from("<I", blob, 1)[0]
d = bytearray(comptolib.decompress_data(blob[:9+csz]))
d0 = bytes(d)   # 순정 사본 -- 원문검색/원본대조는 여기서 (쓰기 순서 무관하게)

# 0) battle_work(조작힌트 등 172개) 원문검색 제자리 패치 먼저.
#    slot2_work 텍스트영역 스캔은 가나 기준이라 한자만인 라벨(術技を変更 등)이 빠짐.
#    원문검색은 원본 상태에서 해야 하므로 rows 패치보다 먼저 수행.
Tall = json.load(open("tbl_all.json", encoding="utf-8"))
Tall = Tall.get("TBL", Tall)
inv_all = {}
for k, v in Tall.items():
    inv_all.setdefault(v, k)


def enc_jp(s):
    out = bytearray()
    i = 0
    while i < len(s):
        m = TAG4.match(s, i)
        if m:
            out += struct.pack(">H", int(m.group(1), 16))
            i = m.end()
            continue
        m = TAG2.match(s, i)
        if m:
            out += bytes([int(m.group(1), 16)])
            i = m.end()
            continue
        c = s[i]
        v = inv_all.get(c)
        if v is not None:
            out += bytes.fromhex(v)
            i += 1
            continue
        if ord(c) < 0x80:
            out += bytes([ord(c)])
            i += 1
            continue
        return None
    return bytes(out)


# ★ 배치 완전 보존 인코딩 (2026-07-16 크래시 근본수정)
#   슬롯2 텍스트 블록은 게임이 통째로 파싱하므로(태그/널 위치 민감),
#   kr 을 jp 와 '바이트 단위 동일 배치'로 쓴다:
#   - 태그(<XX>/<XXXX>)는 원본과 같은 오프셋에
#   - 텍스트 세그먼트는 jp 세그먼트 길이에 공백(0x20) 패딩으로 정확히 일치
#   - 세그먼트가 jp 보다 길면 그 행 전체를 원문 유지 + 리포트 (축약 필요)
TAGSEQ = re.compile(r"<[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{4}>")


def tag_bytes(t):
    h = t[1:-1]
    return bytes.fromhex(h) if len(h) == 4 else bytes([int(h, 16)])


def jp_bytes(jp_s):
    """jp 문자열(태그 포함)의 원본 바이트열. 실패 시 None."""
    tj = TAGSEQ.findall(jp_s)
    out = bytearray()
    for n, sj in enumerate(TAGSEQ.split(jp_s)):
        bj = enc_jp(sj)
        if bj is None:
            return None
        out += bj
        if n < len(tj):
            out += tag_bytes(tj[n])
    return bytes(out)


def enc_layout(jp_s, kr_s):
    """kr 을 jp 와 동일한 바이트 배치로 인코딩. 실패 시 (None, 사유)."""
    tj = TAGSEQ.findall(jp_s)
    tk = TAGSEQ.findall(kr_s)
    if tj != tk:
        return None, f"태그열 불일치 jp={''.join(tj)} kr={''.join(tk)}"
    segs_j = TAGSEQ.split(jp_s)
    segs_k = TAGSEQ.split(kr_s)
    out = bytearray()
    for n, (sj, sk) in enumerate(zip(segs_j, segs_k)):
        bj = enc_jp(sj)
        if bj is None:
            return None, f"jp인코딩불가 seg{n} {sj!r}"
        bk, bad = enc(sk)
        if bk is None:
            return None, f"kr인코딩불가 {bad!r}"
        if len(bk) > len(bj):
            return None, f"seg{n} 초과 {len(bk)}>{len(bj)} {sk!r}"
        out += bk + b" " * (len(bj) - len(bk))
        if n < len(tj):
            out += tag_bytes(tj[n])
    return bytes(out), None


# 쓰기 정책 (2026-07-16 확정):
#  - STRICT 존(조작힌트 연결블록)만 배치 보존(enc_layout, 공백 패딩) -- 표시 실측 요구
#  - 그 외는 kr + 널채움. 후행 <01> 체인은 제거(빈 줄 표시용일 뿐, 널런이 압축에 유리)
#  - ★ 압축 결과가 BLOB2_OFF(310976) 이내여야 함: 슬롯2 blob 는 다중 서브블롭
#    구조로, 첫 스트림 뒤 0xCD 필러 다음 @310976 에 배틀 종료 오버레이 ELF 가 있다.
#    이걸 침범/삭제하면 배틀 종료 시 Invalid Memory Access 크래시 (하루 걸려 규명).
STRICT_LO, STRICT_HI = 273900, 274900
BLOB2_OFF = 310976
TRAIL01 = re.compile(r"(<01>)+$")

bw = json.load(open("work/battle/battle_work.json", encoding="utf-8"))
bw_ok = 0
bw_probs = []
for w in bw:
    kr = (w.get("kr") or "").strip()
    if not kr:
        continue
    full_jb = jp_bytes(w.get("jp", ""))
    if full_jb is None:
        continue
    p = d0.find(full_jb)
    if p < 0:
        continue
    if STRICT_LO <= p <= STRICT_HI:
        nb, why = enc_layout(w.get("jp", ""), kr)
        if nb is None:
            bw_probs.append((w.get("jp", "")[:20], why))
            continue
        if not check:
            d[p:p+len(nb)] = nb
    else:
        kb, _bad = enc(TRAIL01.sub("", kr))
        if kb is None or len(kb) > len(full_jb):
            bw_probs.append((w.get("jp", "")[:20], "초과/인코딩불가"))
            continue
        if not check:
            d[p:p+len(kb)] = kb
            for x in range(p+len(kb), p+len(full_jb)):
                d[x] = 0
    bw_ok += 1
print(f"[battle_work 원문검색] {bw_ok}개 / 스킵 {len(bw_probs)}")
for j, why in bw_probs[:10]:
    print(f"  [bw스킵] {j!r}: {why}")

rows = json.load(open("work/battle_jp/slot2_work.json", encoding="utf-8"))
ok = skip = over = err = 0
probs = []
for r in rows:
    kr = (r.get("kr") or "").strip()
    if not kr:
        skip += 1
        continue
    off = r["off"]
    jb = jp_bytes(r["jp"])
    if jb is None:
        err += 1
        probs.append((off, "jp 인코딩 실패", r["jp"][:30]))
        continue
    if d0[off:off+len(jb)] != jb:
        err += 1
        probs.append((off, "원본 불일치(오프셋 어긋남?)", r["jp"][:30]))
        continue
    if STRICT_LO <= off <= STRICT_HI:
        nb, why = enc_layout(r["jp"], kr)
        if nb is None:
            over += 1
            probs.append((off, why, kr[:30]))
            continue
        if not check:
            d[off:off+len(nb)] = nb
    else:
        e, bad = enc(TRAIL01.sub("", kr))
        if e is None:
            err += 1
            probs.append((off, f"인코딩불가 {bad!r}", kr[:30]))
            continue
        if len(e) + 1 > r["avail"]:
            over += 1
            probs.append((off, f"초과 {len(e)+1}>{r['avail']}", kr[:30]))
            continue
        if not check:
            d[off:off+len(e)] = e
            for q in range(off+len(e), off+r["avail"]):
                d[q] = 0
    ok += 1

print(f"[{'검사' if check else '적용'}] OK {ok} / 빈칸 {skip} / 초과 {over} / 에러 {err}")
for off, msg, kr in probs[:30]:
    print(f"  @{off}: {msg}  kr={kr!r}")

# over(세그먼트 초과)는 해당 행만 원문 유지하므로 적용을 막지 않는다.
# err(원본 불일치/길이 산출 실패)는 구조 문제이므로 중단.
if check or err:
    sys.exit(0 if err == 0 else 1)

# 재압축 -> 첫 스트림만 교체. ★BLOB2_OFF 이후(오버레이 ELF들)는 원본 그대로 보존★
recomp = comptolib.compress_data(bytes(d), version=3)
orig_slot = ptrs[3] - ptrs[2]
print(f"재압축 {len(recomp)}B / 블롭2 시작 {BLOB2_OFF}B -> "
      f"{'OK' if len(recomp)<=BLOB2_OFF else '초과! 텍스트를 줄여야 함'}")
if len(recomp) > BLOB2_OFF:
    sys.exit(1)

new_blob = recomp + b"\xCD" * (BLOB2_OFF - len(recomp)) + blob[BLOB2_OFF:]
assert len(new_blob) == orig_slot
dat = bytearray(open(target, "rb").read())
s0, s1 = ptrs[2], ptrs[3]   # 슬롯2는 폰트/씬보다 앞이라 위치 불변
dat[s0:s1] = new_blob
open(target, "wb").write(bytes(dat))
print(f"[OK] {target} 슬롯2 갱신 (크기불변 {len(dat)}B, 블롭2+ 오버레이 보존)")
