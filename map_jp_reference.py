#!/usr/bin/env python3
# ============================================================
#  map_jp_reference.py
#
#  CN 베이스 번역 JSON의 참조 텍스트(jp 필드)를 "실제 일본어"로 교체.
#
#  이유: CN THEIRSCE는 중국어라 번역 참조로 불편(중국어->한국어 어려움).
#        JP DAT의 같은 씬 THEIRSCE(comptolib 압축)를 풀어 실제 일본어를 뽑고,
#        Strings 섹션의 <Id>로 매칭해 translation/{씬}.json 의 jp 필드에 주입.
#        JP/CN THEIRSCE는 Id 시퀀스가 동일해 1:1 정렬됨(검증 완료).
#
#  kr(번역)은 건드리지 않음. jp 필드만 교체. 빌드는 kr+Id로만 동작하므로 안전.
#  최초 1회 translation/{씬}.json.bak (CN 원본) 백업 생성.
#
#  사용:
#    py map_jp_reference.py --scene 4246
#    py map_jp_reference.py --all
#    py map_jp_reference.py --scene 4246 --dat DAT.BIN --eboot ULJS00132_EBOOT.BIN
# ============================================================
import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

PYTHONLIB_PATH = r"D:\PythonLib"
PTR = 0x126F90


def _utf8_env():
    """자식 프로세스 UTF-8 강제 (콘솔 mojibake 방지)."""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env


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


def extract_slot(dat_path, eboot_path, idx):
    dat_size = os.path.getsize(dat_path)
    ptrs = read_pointers(eboot_path, dat_size)
    if idx + 1 >= len(ptrs):
        raise ValueError(f"슬롯 {idx} 범위 초과 (총 {len(ptrs)-1})")
    with open(dat_path, "rb") as f:
        f.seek(ptrs[idx])
        return f.read(ptrs[idx + 1] - ptrs[idx])


def decompress_sce(container):
    """이벤트 컨테이너에서 THEIRSCE의 comptolib(SCE) 블록을 찾아 압축 해제.
    JP는 타입1/3 압축. SCE 헤더는 THEIRSCE 리터럴 직전 9~수십 바이트 이내.
    -> [타입][압축크기4][해제크기4][LZSS...] 형태를 역스캔으로 탐색."""
    sys.path.insert(0, PYTHONLIB_PATH)
    from pythonlib.utils import comptolib
    t = container.find(b"THEIRSCE")
    if t < 0:
        raise ValueError("THEIRSCE 없음")
    for hdr in range(t - 9, t - 40, -1):
        if hdr < 0:
            break
        typ = container[hdr]
        if typ not in (0, 1, 3):
            continue
        csz, dsz = struct.unpack_from("<II", container, hdr + 1)
        if not (0 < dsz < 5_000_000 and 0 < csz < 2_000_000):
            continue
        try:
            dec = comptolib.decompress_data(container[hdr:hdr + 9 + csz])
            if dec[:8] == b"THEIRSCE":
                return dec, typ, csz
        except Exception:
            pass
    raise ValueError("SCE(THEIRSCE 압축블록) 시작을 못 찾음")


def jp_id_map(scene, dat, eboot, tbl, work_dir, pipeline):
    """JP 슬롯 -> SCE 해제 -> extract -> {Id: 일본어} (Strings 섹션 기준)."""
    container = extract_slot(dat, eboot, scene)
    theirsce, typ, csz = decompress_sce(container)
    Path(work_dir).mkdir(parents=True, exist_ok=True)
    tb = str(Path(work_dir) / f"{scene}_jp_theirsce.bin")
    xml = str(Path(work_dir) / f"{scene}_jp.xml")
    Path(tb).write_bytes(theirsce)
    print(f"    JP SCE 해제: 타입{typ} {csz}B -> {len(theirsce)}B")
    r = subprocess.run(
        [sys.executable, pipeline, "extract", "--bin", tb, "--tbl", tbl, "--out", xml],
        env=_utf8_env(),
    )
    if r.returncode != 0:
        raise RuntimeError("story_pipeline extract 실패")

    from lxml import etree
    root = etree.parse(xml).getroot()
    sroot = root.find(".//Strings")
    entries = (sroot.findall(".//Entry") if sroot is not None
               else root.findall(".//Entry"))
    m = {}
    for e in entries:
        ide = e.find("Id")
        jp = e.find("JapaneseText")
        if ide is not None and ide.text is not None and ide.text.strip() != "-1":
            m[ide.text.strip()] = (jp.text if (jp is not None and jp.text) else "")
    return m


def update_scene(scene, args):
    tj = Path(args.trans_dir) / f"{scene}.json"
    if not tj.exists():
        print(f"[!] {tj} 없음 - 스킵")
        return
    print(f"[i] 씬 {scene}: JP 참조 추출 중...")
    m = jp_id_map(scene, args.dat, args.eboot, args.tbl, args.work_dir, args.pipeline)

    data = json.load(open(tj, encoding="utf-8"))
    # 최초 1회 CN 원본 백업
    bak = tj.with_suffix(".json.bak")
    if not bak.exists():
        bak.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"    백업 생성: {bak.name}")

    changed = missing = 0
    for line in data["lines"]:
        key = str(line["id"])
        if key in m:
            if line.get("jp") != m[key]:
                line["jp"] = m[key]
                changed += 1
        else:
            missing += 1
    json.dump(data, open(tj, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[OK] 씬 {scene}: jp 교체 {changed}개, 매칭실패 {missing}개, 총 {len(data['lines'])}줄")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=int, help="씬 번호")
    ap.add_argument("--all", action="store_true", help="translation/의 모든 씬")
    ap.add_argument("--dat", default="DAT.BIN", help="JP DAT")
    ap.add_argument("--eboot", default="ULJS00132_EBOOT.BIN", help="JP 복호화 EBOOT")
    ap.add_argument("--tbl", default="tbl_all.json", help="코드테이블(추출용)")
    ap.add_argument("--trans-dir", default="translation")
    ap.add_argument("--work-dir", default="work")
    ap.add_argument("--pipeline", default="story_pipeline_bin.py")
    args = ap.parse_args()

    if args.all:
        scenes = sorted(int(p.stem) for p in Path(args.trans_dir).glob("*.json")
                        if p.stem.isdigit())
    elif args.scene is not None:
        scenes = [args.scene]
    else:
        print("[!] --scene 또는 --all 필요", file=sys.stderr)
        sys.exit(1)

    for sc in scenes:
        try:
            update_scene(sc, args)
        except Exception as e:
            print(f"[!] 씬 {sc} 실패: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
