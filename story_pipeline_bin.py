#!/usr/bin/env python3
# ============================================================
#  BIN THEIRSCE 번역 파이프라인 (CN 표준 THEIRSCE 기준)
#
#  BIN 파일 안의 표준 THEIRSCE 블록을 추출해 XML로 뽑고,
#  번역된 XML을 다시 재삽입(포인터 자동 재계산) → BIN에 되넣기.
#  CN판(깨끗한 표준 THEIRSCE)에서 작동. 자유 길이 편집.
#
#  준비: PythonLib(comptolib.dll, lxml), tbl_all.json
#
#  추출:  py story_pipeline_bin.py extract --bin 04246.bin --tbl tbl_all.json --out 04246.xml
#  재삽입: py story_pipeline_bin.py insert --bin 04246.bin --tbl tbl_all.json --xml 04246.xml --out 04246_kr.bin
# ============================================================
import sys, json, struct, argparse, types
from pathlib import Path

PYTHONLIB_PATH = r"D:\PythonLib"

def make_mini(tbl_path):
    for mod in ['pycdlib','pandas','pygsheets','googleapiclient',
                'googleapiclient.errors','pyjson5','tqdm']:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    sys.modules['googleapiclient.errors'].HttpError = Exception
    sys.modules['pyjson5'].load = lambda f: json.load(f)
    sys.modules['pyjson5'].loads = lambda s: json.loads(s)
    sys.modules['tqdm'].tqdm = lambda x, *a, **k: x
    from pythonlib.games.ToolsTOR import ToolsTOR
    from pythonlib.formats.rebirth.theirsce_instructions import InstructionType

    class MiniTOR(ToolsTOR):
        def __init__(self, tbl_path):
            raw = json.load(open(tbl_path, encoding="utf-8"))
            self.jsonTblTags = {k: {int(k2,16): v2 for k2,v2 in v.items()}
                                for k, v in raw.items()}
            if 'TAGS' not in self.jsonTblTags: self.jsonTblTags['TAGS'] = {}
            self.ijsonTblTags = {k: {v2: k2 for k2,v2 in v.items()}
                                 for k, v in self.jsonTblTags.items()}
            self.id = 1
            self.string_opcode = InstructionType.STRING
            self.list_status_insertion = ['Done','To Do','Editing','Proofreading']
            self.repo_path = "."
    return MiniTOR(tbl_path)

def find_theirsce(d):
    """BIN 안의 THEIRSCE 블록 위치와 크기 반환"""
    pos = d.find(b'THEIRSCE')
    if pos < 0:
        return None, None
    # 블록 끝: 다음 THEIRSCE 또는 파일끝. 크기는 헤더로 추정 불가하니 파일끝까지.
    # 표준 THEIRSCE는 str_off + 문자열길이. 안전하게 파일끝까지 잡되,
    # 컨테이너에 뒷 데이터 있으면 별도 처리 필요.
    return pos, len(d) - pos

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["extract","insert"])
    ap.add_argument("--bin", required=True)
    ap.add_argument("--tbl", required=True)
    ap.add_argument("--xml", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sys.path.insert(0, PYTHONLIB_PATH)
    from pythonlib.formats.rebirth.theirsce import Theirsce

    mini = make_mini(args.tbl)
    d = Path(args.bin).read_bytes()
    pos, size = find_theirsce(d)
    if pos is None:
        print("THEIRSCE 블록 없음"); return
    print(f"THEIRSCE @0x{pos:X}")
    block = d[pos:]

    if args.mode == "extract":
        theirsce = Theirsce(block)
        xml_bytes = mini.get_xml_from_theirsce(theirsce, "Story")
        Path(args.out).write_bytes(xml_bytes)
        print(f"추출 완료 -> {args.out}")
    else:
        if not args.xml:
            print("--xml 필요"); return
        theirsce = Theirsce(block)
        new_theirsce = mini.get_new_theirsce(theirsce, Path(args.xml))
        new_theirsce.seek(0)
        new_block = new_theirsce.read()
        # BIN에 되넣기: THEIRSCE 앞부분(컨테이너) + 새 블록
        # 주의: 블록 크기 변하면 컨테이너 헤더 갱신 필요할 수 있음
        new_d = d[:pos] + new_block
        Path(args.out).write_bytes(new_d)
        print(f"재삽입 완료 -> {args.out}")
        print(f"  블록 크기: {size} -> {len(new_block)} (차이 {len(new_block)-size})")
        if len(new_block) != size:
            print("[!] 크기 변함 - 컨테이너 헤더/후속블록 확인 필요할 수 있음")

if __name__ == "__main__":
    main()
