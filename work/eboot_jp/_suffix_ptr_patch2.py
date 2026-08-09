# -*- coding: utf-8 -*-
# 접미사 포인터 2차 교정 (2026-08-09) — '앞공백' 부류
#   증상: 월드맵 마을목록 '  발카', 배틀북 적목록 '  마운틴 시프' 등 앞이 한 칸 밀려 보임.
#   원인: JP 가 긴 이름의 '접미사'(문자열 중간 포인터)를 라벨로 재사용하는데
#         (首都バルカ+4 = バルカ / ハイマウンテンシーフ+8 = マウンテンシーフ),
#         한글은 그 오프셋이 단어 경계가 아니라 '공백' 자리라 앞공백이 노출된다.
#   ★1차 스캔(_suffix_ptr_patch.py)이 놓친 이유: 그 필터는 타깃이 널/글자중간일 때만
#     '깨짐'으로 봤는데, 공백은 정상 글자로 디코드돼 통과했다.
#   해법: 라벨을 독립 문자열로 재배치하고 포인터만 갱신(호스트 문구는 그대로 유지).
#   재배치처 = 요리명 블록 널런(0x10A800~0x10DC00). _trim_pad 로 생긴 구역이고
#   포인터 전용 참조가 실증된 곳(멘탈/미스티 재배치 선례). 0xED780 대역은 이미 소진.
#   idempotent: 이미 재배치 영역을 가리키면 건너뛴다.
import json
import os
import struct
import sys

os.chdir(r"D:\clean_project")
BASE = 0x08803000
POOL_LO, POOL_HI = 0x10A800, 0x10DC00

# (포인터 오프셋들, 라벨) — 라벨이 같으면 한 벌만 배치하고 포인터만 나눠 가리킨다
ITEMS = [
    ([0x151840], "발카"),                 # 월드맵 마을목록 (호스트 '수도 발카')
    ([0x1481A0], "밀리차전"),             # 배틀 장소명 (호스트 '분신 밀리차전')
    ([0x148F6C, 0x148F8C], "히트"),       # 배틀 카운터 (호스트 '연속 히트')
    ([0x149080], "아이템 훔침"),          # 특기 라벨 (호스트 '고확률로 아이템 훔침')
    ([0x149638], "마운틴 시프"),          # 적 유닛명 (호스트 '하이 마운틴 시프')
    ([0x148E74, 0x148E78, 0x148E90, 0x148E94], "？"),  # 미확인 값 표시 (KR 은 빈칸이었음)
]

TBL = json.load(open("tbl_full_kr.json", encoding="utf-8"))["TBL"]
ALL = json.load(open("tbl_all.json", encoding="utf-8"))
ALL = ALL.get("TBL", ALL)
ENC = {v: k for k, v in TBL.items()}
ENCA = {v: k for k, v in ALL.items()}


def enc(s):
    out = bytearray()
    for ch in s:
        if ord(ch) < 0x80:
            out.append(ord(ch))
            continue
        code = ENC.get(ch) or ENCA.get(ch)
        if not code:
            raise SystemExit("[!] 폰트/테이블에 없는 글자: %r" % ch)
        out += bytes.fromhex(code)
    return bytes(out)


def free_runs(buf):
    """재배치 풀의 널런 목록 [(시작, 길이)]"""
    runs = []
    i = POOL_LO
    while i < POOL_HI:
        if buf[i]:
            i += 1
            continue
        s = i
        while i < POOL_HI and not buf[i]:
            i += 1
        runs.append((s, i - s))
    return runs


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "EBOOT_jp_new.BIN"
    buf = bytearray(open(path, "rb").read())
    jp = open("ULJS00132_EBOOT.BIN", "rb").read()
    runs = free_runs(buf)
    done = skip = 0

    for ptrs, label in ITEMS:
        cur = struct.unpack_from("<I", buf, ptrs[0])[0] - BASE
        if POOL_LO <= cur < POOL_HI:
            print("[skip] %-12s 이미 재배치됨 @0x%X" % (label, cur))
            skip += 1
            continue
        # 안전검증: 아직 JP 원래 접미사 위치를 가리키고 있어야 한다
        for p in ptrs:
            if struct.unpack_from("<I", buf, p)[0] != struct.unpack_from("<I", jp, p)[0]:
                raise SystemExit("[!] ptr@0x%X 가 JP 원값과 다름 - 중단" % p)

        b = enc(label)
        need = len(b) + 2                        # 앞 널 1 + 문자열 + 종단 널
        for k, (st, ln) in enumerate(runs):
            if ln >= need:
                at = st + 1
                buf[at:at + len(b)] = b
                buf[at + len(b)] = 0
                runs[k] = (at + len(b) + 1, ln - (len(b) + 1))
                for p in ptrs:
                    struct.pack_into("<I", buf, p, BASE + at)
                print("[OK] %-12s -> @0x%X (%dB), 포인터 %s"
                      % (label, at, len(b), ", ".join("0x%X" % p for p in ptrs)))
                done += 1
                break
        else:
            raise SystemExit("[!] %s: 재배치 공간 부족" % label)

    open(path, "wb").write(bytes(buf))
    print("[DONE] %s 적용 %d / 스킵 %d" % (path, done, skip))


if __name__ == "__main__":
    main()
