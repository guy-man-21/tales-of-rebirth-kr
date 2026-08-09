#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_build_from_file.py — font_map.txt(파일)로 폰트 빌드 (긴 --map 우회)

PowerShell에서 2350쌍(15960자)을 --map 인자로 넘기면 문자열이 깨진다.
이 래퍼는 font_map을 '파일에서 읽어' font_insert_hangul.main()을 직접 호출한다.
(명령줄 인자 길이/특수문자 문제 완전 회피)

사용:
  py font_build_from_file.py --font 00014_CN.bin --table 00015_JP.bin ^
     --map-file hangul_font_map.txt --out 00014_hangul_full.bin ^
     [--outline 6 --bold-level 1]

주: font_insert_hangul.py 가 같은 폴더(또는 sys.path)에 있어야 함.
"""
import argparse
import sys
import runpy
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--font', required=True)
    ap.add_argument('--table', required=True)
    ap.add_argument('--map-file', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--outline', type=int, default=None)
    ap.add_argument('--bold-level', type=int, default=None)
    ap.add_argument('--outline-width', type=int, default=None)
    ap.add_argument('--glow', type=int, default=None)
    ap.add_argument('--glow-width', type=int, default=None)
    ap.add_argument('--supersample', type=int, default=None)
    ap.add_argument('--edge-soft', type=float, default=None)
    ap.add_argument('--font-file', default=None)
    ap.add_argument('--script', default='font_insert_hangul.py',
                    help='font_insert_hangul.py 경로')
    args = ap.parse_args()

    # font_map 파일 읽기 + 정제(개행/공백/BOM 제거)
    raw = Path(args.map_file).read_text(encoding='utf-8')
    raw = raw.replace('\ufeff', '').replace('\n', '').replace('\r', '').strip()
    pairs = [p for p in raw.split(',') if p.count(':') == 1]
    mapping = ",".join(pairs)
    print(f"[i] font_map: {len(pairs)}쌍 로드 (파일 {args.map_file})")

    # sys.argv 를 구성해서 font_insert_hangul.main() 을 그대로 호출
    argv = ['font_insert_hangul.py',
            '--font', args.font,
            '--table', args.table,
            '--map', mapping,
            '--out', args.out]
    if args.outline is not None:       argv += ['--outline', str(args.outline)]
    if args.bold_level is not None:    argv += ['--bold-level', str(args.bold_level)]
    if args.outline_width is not None: argv += ['--outline-width', str(args.outline_width)]
    if args.glow is not None:          argv += ['--glow', str(args.glow)]
    if args.glow_width is not None:    argv += ['--glow-width', str(args.glow_width)]
    if args.supersample is not None:   argv += ['--supersample', str(args.supersample)]
    if args.edge_soft is not None:     argv += ['--edge-soft', str(args.edge_soft)]
    if args.font_file:                 argv += ['--font-file', args.font_file]

    print(f"[i] font_insert_hangul 실행 (2350자 렌더 - 수 분 소요될 수 있음)...")
    sys.argv = argv
    # 스크립트를 __main__ 으로 실행
    runpy.run_path(args.script, run_name='__main__')


if __name__ == '__main__':
    main()
