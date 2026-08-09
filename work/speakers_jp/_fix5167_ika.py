# -*- coding: utf-8 -*-
# 씬5167 イカ -> 오징어 재배치 (2026-08-03).
#  식재 조각은 코드 오퍼랜드(48 XX 04 f8 [u16])로 고정 참조되는데 오징어(6B)가 イカ(4B) 슬롯
#  초과 -> 해물(シーフード 10B->4B) 축소분+널 여유로 red/해물 조각을 +2/+4 밀고 오퍼랜드 갱신.
#  새 레이아웃: 오징어+01 @652 / red(오징어판 17B) @660 / 해물+01 @678 (composite@693 불변)
#  오퍼랜드: @0x4d4 658->660, @0x4dc 674->678.
#  ★_sysrestore 5167 실행 후 반드시 이 스크립트 실행 (edit.py 는 이 스크립트를 위임 대상으로
#   등록 - 내부에서 _sysrestore 먼저 호출). idempotent.
import os
import sys
import json
import struct
import subprocess

os.chdir(r"D:\clean_project")
sys.path.insert(0, r"D:\PythonLib"); sys.path.insert(0, ".")
from pythonlib.utils import comptolib
from build_all_jp import parse_blobs
from pythonlib.formats.rebirth.theirsce import Theirsce

# 1) 선행: _sysrestore 5167 (풀 복원+pin. 이미 최신이어도 무해)
env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
r = subprocess.run([sys.executable, "work/speakers_jp/_sysrestore.py", "5167"],
                   capture_output=True, text=True, encoding="utf-8", env=env)
if "[OK]" not in (r.stdout or ""):
    print("[FAIL] _sysrestore 5167 실패:")
    print((r.stdout or "")[-400:])
    sys.exit(1)
print("[1/2] _sysrestore 5167 완료")

TKR = {k.lower(): v for k, v in json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"].items()}
IK = {}
for k, v in TKR.items():
    IK.setdefault(v, k)
TALL = {k.lower(): v for k, v in json.load(open("tbl_all.json", encoding="utf-8"))["TBL"].items()}
IA = {}
for k, v in TALL.items():
    IA.setdefault(v, k)


def enck(s):
    return b"".join(bytes.fromhex(IK[c]) for c in s)


def enca(s):
    return b"".join(bytes.fromhex(IA[c]) for c in s)


def rp(buf, ds, ptr=0x126F90):
    p = []; k = 0
    while True:
        v = struct.unpack_from("<I", buf, ptr + k * 4)[0]
        if k > 0 and (v < p[-1] or v > ds * 1.05):
            break
        p.append(v); k += 1
        if k > 40000:
            break
    return p


dat = bytearray(open("DAT_jp_final.BIN", "rb").read())
dp = rp(open("EBOOT_jp_new.BIN", "rb").read(), len(dat))
SC = 5167
p0 = dp[SC]; base = dat.rfind(b"SCPK", max(0, p0 - 64), p0 + 8)
nf = struct.unpack_from("<I", dat, base + 8)[0]
sizes = [struct.unpack_from("<I", dat, base + 16 + 4 * k)[0] for k in range(nf)]
cont = bytes(dat[base:base + 16 + 4 * nf + sum(sizes)])
blobs = parse_blobs(cont)
_, boff, bsize, idx = next(bb for bb in blobs if bb[0] == "sce")
raw0 = comptolib.decompress_data(cont[boff:boff + bsize])
so = Theirsce(bytes(raw0)).strings_offset
rs = bytearray(raw0)

IKA = enca("イカ")
OJI = enck("오징어")
HAE = enck("해물")

if rs[so + 652:so + 652 + 6] == OJI and bytes(rs[so + 686:so + 692]) == b"select":
    print("[SKIP] 이미 오징어 적용됨")
    sys.exit(0)
if rs[so + 652:so + 652 + 6] == OJI:
    # 재실행 복구 경로: select@686 유실본 수리만
    rs[so + 686:so + 692] = b"select"
    print("[복구] select@686 재기록")
else:
    assert rs[so + 652:so + 652 + 4] == IKA, "plain slot != イカ (레이아웃 상이)"
    red = bytes(rs[so + 658:so + 673])          # 15B red unit (イカ 포함)
    assert IKA in red, "red slot에 イカ 없음"
    assert rs[so + 674:so + 674 + 4] == HAE, "seafood slot != 해물"
    assert bytes(rs[so + 686:so + 692]) == b"select", "select@686 부재"
    # 코드 오퍼랜드 검증
    assert struct.unpack_from("<H", rs, 0x4d4)[0] == 658, "operand@0x4d4 != 658"
    assert struct.unpack_from("<H", rs, 0x4dc)[0] == 674, "operand@0x4dc != 674"
    # 재배치 (★rel686 'select' ASCII 문자열 보존 필수 - 1차 시도서 널로 덮어 select 서수
    #  -1 사고. 빈 키 유닛 () = ASCII 문자열일 수 있음)
    red_new = red.replace(IKA, OJI)             # 17B
    region = bytearray(41)                       # rel 652..692 (693 직전까지)
    region[0:7] = OJI + b"\x01"                  # @652..658
    region[8:8 + len(red_new)] = red_new         # @660..676
    region[26:31] = HAE + b"\x01"                # @678..682
    region[34:40] = b"select"                    # @686..691
    rs[so + 652:so + 693] = region
    struct.pack_into("<H", rs, 0x4d4, 660)
    struct.pack_into("<H", rs, 0x4dc, 678)
assert rs[so + 692] == 0 and bytes(rs[so + 686:so + 692]) == b"select"

# 재압축 -> 블롭 슬롯 제자리
new = bytes(rs)
blob = comptolib.compress_data(new, version=cont[boff])
how = "greedy"
if len(blob) > bsize:
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("sp", "work/synopsis_jp/_spaced_inplace.py")
    mod = ilu.module_from_spec(spec); spec.loader.exec_module(mod)
    INIT = open("work/synopsis_jp/lzss_init.bin", "rb").read()
    body = mod.lzss_encode_optimal(new, INIT)
    blob = struct.pack("<b", 1) + struct.pack("<L", len(body)) + struct.pack("<L", len(new)) + body
    assert comptolib.decompress_data(blob) == new
    how = "optimal"
assert len(blob) <= bsize, f"blob over {len(blob)-bsize}B"
newc = cont[:boff] + blob + b"#" * (bsize - len(blob)) + cont[boff + bsize:]
dat[base:base + len(newc)] = newc
open("DAT_jp_final.BIN", "wb").write(bytes(dat))
print(f"[2/2] [OK] scene 5167 ika->ojingeo (blob {len(blob)}/{bsize}B, {how})")
print("[SAVED]")
