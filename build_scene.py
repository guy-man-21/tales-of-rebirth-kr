#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_scene.py - 씬 하나를 DAT에서 뽑아 한국어 THEIRSCE까지 자동 생성

흐름 (repack 제외, 빠름):
  CN DAT 슬롯 N 추출 -> story_pipeline extract -> translation/N.json 주입
  -> story_pipeline insert(--tbl tbl_full_kr.json) -> build/N_kr.bin

번역 데이터: translation/{scene}.json
  {
    "scene": 4246,
    "lines": [
      {"id": 9,  "speaker": "Veigue", "jp": "...", "kr": "누구냐......<nl>..."},
      {"id": 10, "speaker": "Mao",    "jp": "...", "kr": ""}   # kr 비면 원문 유지
    ]
  }

사용:
  py build_scene.py --scene 4246
  py build_scene.py --scene 4246 --dat DAT_cn.BIN --eboot EBOOT_DEC.BIN --tbl tbl_full_kr.json
"""
import argparse
import json
import struct
import subprocess
import sys
import os
from pathlib import Path

PTR = 0x126F90



def _utf8_env():
    """자식 프로세스가 UTF-8로 출력하도록 (콘솔 mojibake 방지)."""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env

def read_pointers(eboot_path, dat_size, ptr_base):
    eboot = Path(eboot_path).read_bytes()
    ptrs, i = [], 0
    while True:
        off = ptr_base + i * 4
        if off + 4 > len(eboot):
            break
        v = struct.unpack_from("<I", eboot, off)[0]
        if i > 0 and (v < ptrs[-1] or v > dat_size * 1.05):
            break
        ptrs.append(v); i += 1
        if i > 40000:
            break
    return ptrs


def extract_slot(dat_path, eboot_path, idx, out_path, ptr_base):
    import os
    dat_size = os.path.getsize(dat_path)
    ptrs = read_pointers(eboot_path, dat_size, ptr_base)
    if idx + 1 >= len(ptrs):
        raise ValueError(f"슬롯 {idx} 범위 초과 (총 {len(ptrs)-1})")
    with open(dat_path, "rb") as f:
        f.seek(ptrs[idx])
        data = f.read(ptrs[idx + 1] - ptrs[idx])
    Path(out_path).write_bytes(data)
    return len(data)


def run(cmd):
    print("  $", " ".join(cmd))
    # 출력을 캡처하지 않고 콘솔로 직접 흘림 (자식 프로세스 인코딩 문제 회피).
    # story_pipeline 출력이 CP949라 utf-8 캡처 시 UnicodeDecodeError 발생하므로.
    r = subprocess.run(cmd, env=_utf8_env())
    if r.returncode != 0:
        raise SystemExit(f"명령 실패: {cmd[0]}")
    return ""


def inject_translation(xml_in, xml_out, lines, field="EnglishText"):
    """번역 JSON의 lines를 XML에 주입 (lxml).
    JSON의 'id'는 XML <Id> 태그 값과 매칭한다 (문서순 인덱스 아님).
    대사는 <Strings> 섹션에 있으므로 거기서만 Id를 찾는다."""
    from lxml import etree
    tree = etree.parse(xml_in, etree.XMLParser())
    root = tree.getroot()
    strings_root = root.find('.//Strings')
    target_entries = (strings_root.findall('.//Entry')
                      if strings_root is not None else root.findall('.//Entry'))
    by_id = {}
    for e in target_entries:
        ide = e.find('Id')
        if ide is not None and ide.text is not None:
            by_id[ide.text.strip()] = e

    n = 0
    for line in lines:
        kr_raw = line.get('kr') or ''
        if not kr_raw.strip():
            continue
        # 앞 공백(전각 포함)은 보존 - 선택지 행별 들여쓰기가 앞 전각공백에 의존 (2026-07-30).
        # 뒤 공백/개행 제거하되, ★JP 꼬리에 개행이 있으면 JP 꼬리를 그대로 복원 (2026-08-02):
        #  select 목록형 옵션은 후행 '　\n'(<8140><01>)이 행 구분자 - 제거하면 옵션들이
        #  한 행으로 병합됨 (씬4619 발카항 정기선 램덤프 실증). 종전 '표시 무해' 판정은 오판.
        kr = kr_raw.rstrip()
        jp_raw = line.get('jp') or ''
        jp_tail = jp_raw[len(jp_raw.rstrip('\n　 ')):]
        if '\n' in jp_tail:
            # TAILMODE=min: 압축예산 빡빡한 씬용 - 꼬리 공백은 버리고 개행만 복원(행 구분 유지)
            if os.environ.get('TAILMODE') == 'min':
                jp_tail = '\n' * jp_tail.count('\n')
            kr += jp_tail
        key = str(line['id'])
        e = by_id.get(key)
        if e is None:
            print(f"  [!] Id {key} 를 Strings에서 못 찾음", file=sys.stderr); continue
        el = e.find(field)
        if el is None:
            el = etree.SubElement(e, field)
        el.text = kr
        n += 1
    tree.write(xml_out, encoding='utf-8', xml_declaration=False)
    return n


def make_template(xml_path, trans_js, scene, field="EnglishText"):
    """extract된 XML의 <Strings> 섹션에서 대사 엔트리를 골라 번역 JSON 뼈대 생성.
    'id'는 XML <Id> 태그 값 (inject_translation 과 동일 기준)."""
    from lxml import etree
    tree = etree.parse(xml_path, etree.XMLParser())
    root = tree.getroot()
    strings_root = root.find('.//Strings')
    entries = (strings_root.findall('.//Entry')
               if strings_root is not None else root.findall('.//Entry'))
    lines = []
    for e in entries:
        ide = e.find('Id')
        if ide is None or ide.text is None or ide.text.strip() == '-1':
            continue
        sp = e.find('SpeakerId')
        jp = e.find('JapaneseText')
        vid = e.find('VoiceId')
        jp_txt = jp.text if (jp is not None and jp.text) else ''
        # 실제 대사만: SpeakerId 있는 것 (없으면 시스템 문자열일 수 있음 - 포함하되 표시)
        lines.append({
            'id': ide.text.strip(),
            'speaker': (sp.text if (sp is not None and sp.text) else ''),
            'voice': (vid.text if (vid is not None and vid.text) else ''),
            'jp': jp_txt,
            'kr': ''
        })
    data = {'scene': scene, 'lines': lines}
    Path(trans_js).parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(trans_js, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return len(lines)


TAIL_MAX = 256   # THEIRSCE 데이터 뒤 꼬리(정렬패딩 + SCPK 푸터)의 최대 크기


def fix_container(orig_path, inserted_path, out_path):
    """새 THEIRSCE를 원본 데이터 크기 자리에 넣고, 뒤 꼬리를 그대로 보존.

    원본 컨테이너 구조:
        [그래픽][THEIRSCE 데이터 D바이트][꼬리 (정렬패딩 + SCPK 푸터)]
    크기테이블(파일 앞부분)에 D가 적혀 있고, 게임은 그 값으로 THEIRSCE를 읽는다.

    하는 일:
      1) 크기테이블에서 D 항목을 찾는다 (영역크기와의 차이 = 꼬리 길이).
         꼬리는 씬마다 11~87B로 제각각이라 문턱을 TAIL_MAX 까지 넉넉히 본다.
         (구버전은 64로 잡아서 꼬리 87B인 씬 280개를 못 찾고 실패했다)
      2) 새 THEIRSCE를 D 크기에 맞춰 0패딩한다.
      3) **원본 꼬리를 원래 위치에 그대로 되붙인다.**
         구버전은 여기를 0으로 덮어써서 SCPK 푸터를 날렸다
         (_archive/fix_scpk_tail.py 가 "간헐적 크래시" 원인으로 지목한 부분).
      4) 크기테이블 항목을 새 데이터 크기로 갱신.
    전체 파일 크기는 불변 -> 뒤 서브파일/음성 오프셋이 밀리지 않는다.

    반환: (성공, 메시지)"""
    import struct
    orig = bytearray(Path(orig_path).read_bytes())
    ins = Path(inserted_path).read_bytes()
    ot = orig.find(b'THEIRSCE')
    it = ins.find(b'THEIRSCE')
    if ot < 0 or it < 0:
        return False, "THEIRSCE 못 찾음"
    if orig[:ot] != ins[:it]:
        return False, "그래픽부가 원본과 다름"

    orig_area = len(orig) - ot        # THEIRSCE ~ EOF (데이터 + 꼬리)
    new_data = ins[it:]               # 새 THEIRSCE 데이터 (story_pipeline 결과)
    new_len = len(new_data)

    # 1) 크기테이블에서 THEIRSCE 데이터 크기 D 찾기.
    #    영역크기보다 작되 가장 가까운 값 = D (차이가 곧 꼬리 길이)
    best = None
    for i in range(40):
        if (i + 1) * 4 > len(orig):
            break
        v = struct.unpack_from('<I', orig, i * 4)[0]
        if 0 < v <= orig_area and (orig_area - v) <= TAIL_MAX:
            if best is None or v > best[1]:
                best = (i, v)
    if best is None:
        return False, f"크기테이블에서 THEIRSCE 크기(~{orig_area}) 못 찾음"
    size_idx, orig_len = best
    tail = bytes(orig[ot + orig_len:])   # 2) 원본 꼬리

    if new_len > orig_len:
        return False, (f"THEIRSCE가 원본보다 {new_len - orig_len}B 큼 "
                       f"({orig_len} -> {new_len}) - 번역 줄여야 함")

    # 3) 새 데이터 + 0패딩 + 원본 꼬리  (총 크기 불변)
    pad = orig_len - new_len
    out = bytearray(ins[:it]) + bytearray(new_data) + b'\x00' * pad + tail
    if len(out) != len(orig):
        return False, f"크기 불일치 {len(out)} != 원본 {len(orig)}"

    # 4) 크기테이블 갱신
    struct.pack_into('<I', out, size_idx * 4, new_len)
    Path(out_path).write_bytes(bytes(out))
    return True, (f"크기테이블[{size_idx}] {orig_len}->{new_len}, "
                  f"패딩 {pad}B, 꼬리 {len(tail)}B 보존, 크기 일치")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', type=int, required=True)
    ap.add_argument('--dat', default='DAT_cn.BIN')
    ap.add_argument('--eboot', default='EBOOT_DEC.BIN')
    ap.add_argument('--tbl', default='tbl_full_kr.json')
    ap.add_argument('--trans-dir', default='translation')
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--work-dir', default='work')
    ap.add_argument('--pipeline', default='story_pipeline_bin.py')
    ap.add_argument('--ptr', type=lambda x: int(x, 0), default=PTR)
    ap.add_argument('--field', default='EnglishText')
    ap.add_argument('--make-template', action='store_true',
                    help='번역 JSON 뼈대만 생성하고 종료 (추출->템플릿)')
    ap.add_argument('--jp-dat', default='DAT.BIN', help='JP DAT (참조 일본어 추출용)')
    ap.add_argument('--jp-eboot', default='ULJS00132_EBOOT.BIN', help='JP 복호화 EBOOT')
    ap.add_argument('--no-jp-ref', action='store_true',
                    help='템플릿 생성 시 jp를 일본어로 채우지 않고 CN 원문 유지')
    args = ap.parse_args()

    scene = args.scene
    Path(args.build_dir).mkdir(exist_ok=True)
    Path(args.work_dir).mkdir(exist_ok=True)

    slot_bin = f"{args.work_dir}/{scene}_cn.bin"
    xml_raw  = f"{args.work_dir}/{scene}.xml"
    xml_kr   = f"{args.work_dir}/{scene}_KR.xml"
    raw_bin  = f"{args.work_dir}/{scene}_kr_raw.bin"
    out_bin  = f"{args.build_dir}/{scene}_kr.bin"
    trans_js = f"{args.trans_dir}/{scene}.json"

    # 1) DAT에서 슬롯 추출
    sz = extract_slot(args.dat, args.eboot, scene, slot_bin, args.ptr)
    print(f"[1/5] 슬롯 {scene} 추출: {sz}B -> {slot_bin}")

    # 2) extract -> XML
    print(f"[2/5] extract -> {xml_raw}")
    run(['py', args.pipeline, 'extract', '--bin', slot_bin,
         '--tbl', 'tbl_all.json', '--out', xml_raw])

    # --make-template: 여기서 뼈대 생성하고 종료
    if args.make_template:
        if Path(trans_js).exists():
            print(f"[!] 이미 존재: {trans_js} - 덮어쓰지 않음.")
        else:
            n = make_template(xml_raw, trans_js, scene, args.field)
            print(f"[[OK]] 번역 템플릿 생성: {trans_js} ({n}개 대사)")
            # jp 참조를 실제 일본어로 채움 (기본 동작). CN 원문은 알아보기 어려움.
            if not args.no_jp_ref:
                try:
                    from map_jp_reference import jp_id_map
                    m = jp_id_map(scene, args.jp_dat, args.jp_eboot,
                                  'tbl_all.json', args.work_dir, args.pipeline)
                    data = json.load(open(trans_js, encoding='utf-8'))
                    cnt = 0
                    for line in data['lines']:
                        k = str(line['id'])
                        if k in m:
                            line['jp'] = m[k]; cnt += 1
                    json.dump(data, open(trans_js, 'w', encoding='utf-8'),
                              ensure_ascii=False, indent=1)
                    print(f"[[OK]] jp 참조 -> 일본어 {cnt}개 주입 (CN 아님)")
                except Exception as e:
                    print(f"[!] JP 참조 주입 실패, CN 원문 유지: "
                          f"{type(e).__name__}: {e}", file=sys.stderr)
        return

    # 3) 번역 주입
    if not Path(trans_js).exists():
        print(f"[!] 번역 파일 없음: {trans_js} - 원문 그대로 빌드")
        Path(xml_kr).write_bytes(Path(xml_raw).read_bytes())
        n = 0
    else:
        data = json.load(open(trans_js, encoding='utf-8'))
        n = inject_translation(xml_raw, xml_kr, data.get('lines', []), args.field)
    print(f"[3/5] 번역 주입: {n}줄 -> {xml_kr}")

    # 4) insert (전역 tbl_full_kr) -> raw
    print(f"[4/5] insert (--tbl {args.tbl}) -> {raw_bin}")
    run(['py', args.pipeline, 'insert', '--bin', slot_bin,
         '--tbl', args.tbl, '--xml', xml_kr, '--out', raw_bin])

    # 5) 컨테이너 크기 보존 (원본 크기로 패딩 + SCPK 꼬리 복원)
    ok, msg = fix_container(slot_bin, raw_bin, out_bin)
    print(f"[5/5] 컨테이너 보존: {msg}")
    if not ok:
        print(f"\n[X] 빌드 실패: {msg}", file=sys.stderr)
        sys.exit(3)

    print(f"\n[[OK]] 씬 {scene} 완료 -> {out_bin}")
    print(f"    최종 반영: py build_dat.py --scenes {scene} --font 00014_hangul_full.bin")


if __name__ == '__main__':
    main()
