#!/usr/bin/env python3
# 줄거리(슬롯3969) '부분 띄어쓰기' 제자리 적용 (2026-07-18 최종해법).
#  ★성장(repack) = 배틀종료 크래시(게임이 이 블롭을 고정버퍼로 읽는 정황) -> 성장 금지.
#  ★3널->1널 정규화 = 표시 깨짐 실증(2026-07-18: 조각 첫글자 유실 '클레어'->'레어', 조각 스킵)
#    -> **널런은 원본 그대로 보존** (파서가 널 개수로 조각을 세는 게 확정).
#  해법 = 압축을 원본 footprint(16608B, csize<=16599)에 맞춤:
#   (1) 자체 최적파스 LZSS 인코더 (comptolib v1 역설계: 4096링, r0=0xFEE, INIT 테이블 덤프,
#       리터럴9bit/매치17bit DP). greedy DLL 대비 ~1.6% 절감. DLL 디코더 라운드트립 검증.
#   (2) 공백 전역규칙: 문장부호(,.…!?」』) + 조사 을/를/은/는 뒤만 유지 (695개).
#       균일규칙이라 LZ 효율 좋고 가독성 일관. (이가에로와과까지는 용량 초과)
#   (3) 트림복원분은 하이브리드: 트림판과 어휘가 다른 조각은 트림판(무공백) 사용.
#  소스: synopsis_work_full.json (띄어쓰기판) + synopsis_work.json (트림판).
#  사용: py work\synopsis_jp\_spaced_inplace.py [--check]
import argparse
import json
import os
import re
import struct
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, r"D:\PythonLib")
from pythonlib.utils import comptolib

Tkr = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
inv = {v: int(k, 16) for k, v in Tkr.items()}
TAG = re.compile(r"<([0-9A-Fa-f]{2})>")
PTR = 0x126F90
SLOT = 3969
HDR = 0xB14
FOOT = 16608
CLASSES = set(",.…!?」』" + "을를는")
# '은' 뒤 공백은 문서순 앞 EUN_K 개만 유지 (용량 딱 맞춤: 조사수정 후 16599B 정확 적합.
#  전부 유지하면 +2B 초과. 텍스트 수정 시 이 값 재탐색 필요 - 이진탐색으로 최대 K 찾기.)
EUN_K = 83

# ---------- LZSS v1 (역설계 확정 포맷) ----------
# INIT 테이블: DLL 프로브 덤프본 (없으면 재생성 필요 - scratchpad/lzss_init.bin 참조)
INIT_PATH = os.path.join("work", "synopsis_jp", "lzss_init.bin")


def lzss_decode(body, dsize, init):
    ring = bytearray(init)
    r = 0xFEE
    out = bytearray()
    i = 0
    while len(out) < dsize and i < len(body):
        flag = body[i]
        i += 1
        for b in range(8):
            if len(out) >= dsize or i >= len(body):
                break
            if flag & (1 << b):
                c = body[i]
                i += 1
                out.append(c)
                ring[r] = c
                r = (r + 1) & 0xFFF
            else:
                b1 = body[i]
                b2 = body[i + 1]
                i += 2
                pos = b1 | ((b2 & 0xF0) << 4)
                ln = (b2 & 0x0F) + 3
                for k in range(ln):
                    c = ring[(pos + k) & 0xFFF]
                    out.append(c)
                    ring[r] = c
                    r = (r + 1) & 0xFFF
    return bytes(out)


def lzss_encode_optimal(data, init, chain_cap=512):
    N = len(data)
    mlA = [0] * N
    mjA = [0] * N
    head = {}
    prev = [-1] * N
    for i in range(N):
        if i + 3 <= N:
            key = data[i:i + 3]
            best = 0
            bj = -1
            j = head.get(key, -1)
            steps = 0
            while j >= 0 and steps < chain_cap:
                if j >= i - 4095:
                    L = 3
                    maxL = min(18, N - i)
                    while L < maxL and data[j + L] == data[i + L]:
                        L += 1
                    if L > best:
                        best = L
                        bj = j
                        if best >= min(18, N - i):
                            break
                else:
                    break
                j = prev[j]
                steps += 1
            mlA[i] = best if best >= 3 else 0
            mjA[i] = bj
            prev[i] = head.get(key, -1)
            head[key] = i
    mlB = [0] * N
    mpB = [0] * N
    for i in range(min(N, 4096 + 18)):
        best = 0
        bp = -1
        maxL = min(18, N - i)
        if maxL < 3:
            break
        pat = data[i:i + maxL]
        seed = pat[:3]
        start = 0
        while True:
            p = init.find(seed, start)
            if p < 0 or p + 3 > 4096:
                break
            L = 3
            while L < maxL and p + L < 4096 and init[p + L] == pat[L]:
                L += 1
            ok = True
            for s in range(p, p + L):
                if ((s - 0xFEE) & 0xFFF) < i + L:
                    ok = False
                    break
            while not ok and L > 3:
                L -= 1
                ok = True
                for s in range(p, p + L):
                    if ((s - 0xFEE) & 0xFFF) < i + L:
                        ok = False
                        break
            if ok and L > best:
                best = L
                bp = p
                if best >= maxL:
                    break
            start = p + 1
        if best >= 3:
            mlB[i] = best
            mpB[i] = bp
    cost = [0] * (N + 1)
    for i in range(N - 1, -1, -1):
        c = 9 + cost[i + 1]
        m = max(mlA[i], mlB[i])
        if m >= 3:
            for L in range(3, m + 1):
                if i + L <= N:
                    c2 = 17 + cost[i + L]
                    if c2 < c:
                        c = c2
        cost[i] = c
    ops = []
    i = 0
    while i < N:
        if cost[i] == 9 + cost[i + 1]:
            ops.append(("lit", data[i]))
            i += 1
            continue
        m = max(mlA[i], mlB[i])
        done = False
        for L in range(m, 2, -1):
            if i + L <= N and cost[i] == 17 + cost[i + L]:
                p = (0xFEE + mjA[i]) & 0xFFF if mlA[i] >= L else mpB[i]
                ops.append(("match", p, L))
                i += L
                done = True
                break
        if not done:
            ops.append(("lit", data[i]))
            i += 1
    out = bytearray()
    k = 0
    while k < len(ops):
        grp = ops[k:k + 8]
        flag = 0
        for b, op in enumerate(grp):
            if op[0] == "lit":
                flag |= (1 << b)
        out.append(flag)
        for op in grp:
            if op[0] == "lit":
                out.append(op[1])
            else:
                _, p, L = op
                out.append(p & 0xFF)
                out.append(((p >> 4) & 0xF0) | (L - 3))
        k += 8
    return bytes(out)


# ---------- 텍스트 ----------
def enc_kr(kr):
    out = bytearray()
    i = 0
    while i < len(kr):
        m = TAG.match(kr, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        c = kr[i]
        if c in inv:
            out += struct.pack(">H", inv[c])
        elif ord(c) < 0x80:
            out.append(ord(c))
        else:
            return None
        i += 1
    return bytes(out)


_eun_used = [0]


def filter_spaces(kr):
    out = []
    for ch in kr:
        if ch == " ":
            prev = out[-1] if out else ""
            if prev and prev in CLASSES:
                out.append(ch)
            elif prev == "은" and _eun_used[0] < EUN_K:
                out.append(ch)
                _eun_used[0] += 1
        else:
            out.append(ch)
    return "".join(out)


def read_ptrs(eb, dsize):
    p = []
    j = 0
    while True:
        v = struct.unpack_from("<I", eb, PTR + j * 4)[0]
        if j > 0 and (v < p[-1] or v > dsize * 1.05):
            break
        p.append(v)
        j += 1
        if j > 40000:
            break
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    init = open(INIT_PATH, "rb").read()
    src = open("DAT.BIN", "rb").read()
    sp = read_ptrs(open("ULJS00132_EBOOT.BIN", "rb").read(), len(src))
    lo_s = sp[SLOT] - 32
    csz0 = struct.unpack_from("<I", src, lo_s + 1)[0]
    d = comptolib.decompress_data(bytes(src[lo_s:lo_s + 9 + csz0]))

    rows = json.load(open("work/synopsis_jp/synopsis_work_full.json", encoding="utf-8"))
    tmap = {r["off"]: (r.get("kr") or "").strip()
            for r in json.load(open("work/synopsis_jp/synopsis_work.json", encoding="utf-8"))}
    krmap = {}
    nsp = 0
    for r in rows:
        kr = (r.get("kr") or "").strip()
        if not kr:
            continue
        t = tmap.get(r["off"], "")
        if t and t.replace(" ", "") != kr.replace(" ", ""):
            kr = t                     # 어휘 다르면 트림판(무공백)
        else:
            kr = filter_spaces(kr)
        nsp += kr.count(" ")
        e = enc_kr(kr)
        if e is not None:
            krmap[r["off"]] = e

    out = bytearray(d[:HDR])
    remap = {}
    i = HDR
    while i < len(d):
        if d[i] == 0:
            st = i
            while i < len(d) and d[i] == 0:
                i += 1
            out += b"\x00" * (i - st)   # ★널런 원본 그대로 (개수 민감 실증)
            continue
        st = i
        while i < len(d) and d[i] != 0:
            i += 2 if d[i] >= 0x81 else 1
        remap[st] = len(out)
        out += krmap.get(st, bytes(d[st:i]))
    hits = 0
    for off in range(0, HDR, 4):
        v = struct.unpack_from("<I", out, off)[0]
        if HDR <= v < len(d) and v in remap:
            struct.pack_into("<I", out, off, remap[v])
            hits += 1
    blob = bytes(out)

    body = lzss_encode_optimal(blob, init)
    print(f"[블롭] 해제 {len(blob)}B / 공백 {nsp} / 헤더재매핑 {hits} / 최적압축 {len(body)}B (한도 16599)")
    if len(body) > 16599:
        print("[중단] 한도 초과")
        return
    # 이중 검증: 내 디코더 + DLL 디코더
    if lzss_decode(body, len(blob), init) != blob:
        print("[중단] 자체 디코더 불일치")
        return
    full = struct.pack("<b", 1) + struct.pack("<L", len(body)) + struct.pack("<L", len(blob)) + body
    if comptolib.decompress_data(full) != blob:
        print("[중단] DLL 디코더 불일치")
        return
    print("[검증] 자체/DLL 디코더 라운드트립 OK")

    if args.check:
        return
    dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
    dp = read_ptrs(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
    lo = dp[SLOT] - 32
    if dat[lo] not in (1, 3):
        print(f"[중단] {hex(lo)} 블롭 시작 아님")
        return
    dat[lo:lo + len(full)] = full
    for q in range(lo + len(full), lo + FOOT):
        dat[q] = 0
    open("DAT_jp_final.BIN", "wb").write(bytes(dat))
    print(f"[OK] DAT_jp_final 슬롯{SLOT} 제자리 (크기·footprint 불변, 공백 {nsp}개)")


if __name__ == "__main__":
    main()
