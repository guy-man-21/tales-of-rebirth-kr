#!/usr/bin/env python3
# ============================================================
#  build_all.py -- translation/*.json 이 있는 모든 씬을 한 번에 빌드
#
#  build_scene.py 는 씬마다 story_pipeline 을 하위 프로세스로 2회 띄운다.
#  716씬이면 1432회 -> 너무 느리다. 이 스크립트는 MiniTOR 를 1회만 만들고
#  in-process 로 전 씬을 돈다 (theirsce_xlsx.py 와 같은 방식). 약 1분.
#
#  단계 (씬마다):
#    DAT 슬롯 -> THEIRSCE extract -> 번역 주입 -> insert
#    -> scpk_patch.build_slot (SCPK 컨테이너 정식 해석) -> build/{scene}_kr.bin
#
#  컨테이너 처리는 scpk_patch.py 참고. 요약:
#    - THEIRSCE 는 SCPK 의 한 블롭. 블롭 = comptolib헤더 9B + 데이터.
#    - 새 데이터가 원본 블롭 자리에 들어가면 크기 유지('#' 패딩) -> 아무것도 안 밀림.
#    - 넘치면 블롭을 키우고 크기테이블 갱신. 크기테이블 항목이 이전 슬롯에
#      걸치는 씬이 있어(포인터 오정렬) 그 슬롯도 함께 교체 대상에 넣는다.
#    - DAT 크기 변경은 repack_psp_dat.py 가 EBOOT 포인터를 재계산해 처리한다.
#
#  사용:
#    py build_all.py                    # 전 씬
#    py build_all.py --scenes 4246,4247 # 일부만
# ============================================================
import argparse
import bisect
import json
import struct
import sys
import time
from pathlib import Path

PYTHONLIB_PATH = r"D:\PythonLib"
PTR = 0x126F90


def read_pointers(eboot_path, dat_size, ptr_base=PTR):
    eboot = Path(eboot_path).read_bytes()
    ptrs, i = [], 0
    while True:
        off = ptr_base + i * 4
        if off + 4 > len(eboot):
            break
        v = struct.unpack_from("<I", eboot, off)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size * 1.05):
            break
        ptrs.append(v)
        i += 1
        if i > 40000:
            break
    return ptrs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default="DAT_cn.BIN")
    ap.add_argument("--eboot", default="EBOOT_DEC.BIN")
    ap.add_argument("--tbl-extract", default="tbl_all.json")
    ap.add_argument("--tbl-insert", default="tbl_full_kr.json")
    ap.add_argument("--trans-dir", default="translation")
    ap.add_argument("--build-dir", default="build")
    ap.add_argument("--work-dir", default="work")
    ap.add_argument("--scenes", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="build_report.json")
    ap.add_argument("--no-grow", action="store_true",
                    help="컨테이너를 키우지 않는다. 원본 블롭 자리에 안 들어가는 씬은 "
                         "통째로 건너뛴다(원문 유지). DAT 크기가 원본과 같아지고 "
                         "이전슬롯 교차패치도 생기지 않는다 - 가장 안전한 빌드.")
    ap.add_argument("--no-cross", action="store_true",
                    help="확장은 하되, 크기테이블이 '이전 슬롯'에 걸친 씬만 건너뛴다. "
                         "확장 자체가 문제인지 교차패치가 문제인지 가르는 용도.")
    args = ap.parse_args()

    sys.path.insert(0, PYTHONLIB_PATH)
    sys.path.insert(0, ".")
    from pythonlib.formats.rebirth.theirsce import Theirsce

    from build_scene import inject_translation
    from scpk_patch import build_slot, find_container
    from story_pipeline_bin import make_mini

    Path(args.build_dir).mkdir(exist_ok=True)
    Path(args.work_dir).mkdir(exist_ok=True)

    print("[i] MiniTOR 초기화...")
    mini_ex = make_mini(args.tbl_extract)    # 추출용(원본 코드테이블)
    mini_in = make_mini(args.tbl_insert)     # 삽입용(한글 회수 코드테이블)

    dat = Path(args.dat).read_bytes()
    ptrs = read_pointers(args.eboot, len(dat))
    print(f"[i] DAT {len(dat)}B, 포인터 {len(ptrs)}개")

    if args.scenes:
        scenes = [int(s) for s in args.scenes.split(",") if s.strip()]
    else:
        scenes = sorted(int(p.stem) for p in Path(args.trans_dir).glob("*.json")
                        if p.stem.isdigit())
    if args.limit:
        scenes = scenes[:args.limit]
    print(f"[i] 대상 씬 {len(scenes)}개")

    slots = {}          # slot_idx -> 새 바이트
    pending = []        # 이전 슬롯에 걸친 크기테이블 패치 (절대오프셋, 값)
    ok, grew, err = [], [], []
    t0 = time.time()

    for n, sc in enumerate(scenes, 1):
        try:
            # THEIRSCE 를 '정확한 길이'로 자른다.
            # 예전처럼 매직~슬롯끝을 통째로 넘기면 THEIRSCE 뒤의 UNK 블롭/패딩까지
            # 코드로 파싱하다 죽는다 (씬 4444: ValueError: 5 is not a valid VariableType).
            # 길이는 블롭 앞 comptolib 헤더의 csize 에 정확히 적혀 있다.
            c = find_container(dat, ptrs, sc)
            t = c["theirsce_off"]
            csize = struct.unpack_from("<I", dat, t - 8)[0]
            block = dat[t:t + csize]

            # 1) extract -> XML
            mini_ex.id = 1     # 씬마다 리셋 (누적되면 Id 어긋남)
            xml_raw = f"{args.work_dir}/{sc}.xml"
            Path(xml_raw).write_bytes(
                mini_ex.get_xml_from_theirsce(Theirsce(block), "Story"))

            # 2) 번역 주입
            xml_kr = f"{args.work_dir}/{sc}_KR.xml"
            data = json.load(open(Path(args.trans_dir) / f"{sc}.json",
                                  encoding="utf-8"))
            n_inj = inject_translation(xml_raw, xml_kr, data.get("lines", []))

            # 3) insert -> 새 THEIRSCE
            mini_in.id = 1
            t = mini_in.get_new_theirsce(Theirsce(block), Path(xml_kr))
            t.seek(0)
            new_theirsce = t.read()

            # 4) SCPK 컨테이너에 끼워넣기
            slot, patch, info = build_slot(dat, ptrs, sc, new_theirsce)
            fits = ("슬롯 크기 유지" in info) and not patch
            if args.no_grow and not fits:
                grew.append({"scene": sc, "lines": n_inj,
                             "msg": "[건너뜀 --no-grow] " + info})
                continue
            if args.no_cross and patch:
                grew.append({"scene": sc, "lines": n_inj,
                             "msg": "[건너뜀 --no-cross] " + info})
                continue
            slots[sc] = slot
            if patch:
                pending.append(patch)
            if fits:
                ok.append({"scene": sc, "lines": n_inj, "msg": info})
            else:
                grew.append({"scene": sc, "lines": n_inj, "msg": info})
        except Exception as e:
            err.append({"scene": sc, "why": f"{type(e).__name__}: {e}"})

        if n % 100 == 0 or n == len(scenes):
            el = time.time() - t0
            print(f"  [{n}/{len(scenes)}] 자리유지 {len(ok)} / 확장 {len(grew)} / "
                  f"에러 {len(err)}  ({el:.0f}s)", flush=True)

    # 5) 이전 슬롯에 걸친 크기테이블 패치 적용
    #    그 항목은 해당 슬롯의 '끝에서부터' 센 위치가 불변이다
    #    (앞쪽 THEIRSCE 블롭이 커져도 뒤로 밀리므로).
    cross = 0
    for off, val in pending:
        j = bisect.bisect_right(ptrs, off) - 1
        from_end = ptrs[j + 1] - off
        b = bytearray(slots.get(j, dat[ptrs[j]:ptrs[j + 1]]))
        idx = len(b) - from_end
        if not (0 <= idx <= len(b) - 4):
            err.append({"scene": j, "why": f"크로스패치 위치 이상 {idx}"})
            continue
        struct.pack_into("<I", b, idx, val)
        slots[j] = bytes(b)
        cross += 1

    # 6) 슬롯 파일로 저장
    for sc, b in slots.items():
        Path(f"{args.build_dir}/{sc}_kr.bin").write_bytes(b)

    print("\n" + "=" * 60)
    print(f"빌드 완료: 자리유지 {len(ok)} / 컨테이너확장 {len(grew)} / 에러 {len(err)}")
    print(f"  이전슬롯 크기테이블 패치 {cross}건 (그 슬롯도 함께 교체됨)")
    print(f"  교체할 슬롯 총 {len(slots)}개 -> {args.build_dir}/")
    if err:
        print(f"\n[에러 {len(err)}개]")
        for e in err[:20]:
            print(f"  씬 {e['scene']}: {e['why']}")

    json.dump({"ok": ok, "grew": grew, "err": err, "cross": cross},
              open(args.report, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n리포트 -> {args.report}")
    print("다음: py build_dat.py --all --font 00014_hangul_full.bin")


if __name__ == "__main__":
    main()
