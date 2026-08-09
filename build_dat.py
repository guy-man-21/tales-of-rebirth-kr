#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dat.py - build/*.bin(한국어 씬들) + 폰트를 한 번에 DAT 재패킹

씬별 build_scene.py 로 만든 build/{scene}_kr.bin 들과 한글 폰트를
repack_psp_dat.py 로 한 번에 넣는다. (느린 repack을 씬마다 안 하고 1회로)

사용:
  py build_dat.py --scenes 4246,4247 --font 00014_hangul_full.bin
  py build_dat.py --all --font 00014_hangul_full.bin   # build/ 의 모든 씬
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path



def _utf8_env():
    """자식 프로세스가 UTF-8로 출력하도록 (콘솔 mojibake 방지)."""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenes', default='', help='쉼표구분 씬번호. 예: 4246,4247')
    ap.add_argument('--all', action='store_true', help='build/의 모든 *_kr.bin')
    ap.add_argument('--font', default='00014_hangul_full.bin', help='한글 폰트(슬롯14)')
    ap.add_argument('--font-slot', type=int, default=14)
    ap.add_argument('--dat', default='DAT_cn.BIN')
    ap.add_argument('--eboot', default='EBOOT_DEC.BIN')
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--out-dat', default='DAT_cn_new.BIN')
    ap.add_argument('--out-eboot', default='EBOOT_cn_new.BIN')
    ap.add_argument('--repack', default='repack_psp_dat.py')
    args = ap.parse_args()

    # 씬 목록 수집
    scenes = []
    if args.all:
        for p in sorted(Path(args.build_dir).glob('*_kr.bin')):
            try:
                scenes.append(int(p.stem.split('_')[0]))
            except ValueError:
                pass
    else:
        scenes = [int(s) for s in args.scenes.split(',') if s.strip()]
    if not scenes:
        print("[!] 씬 없음. --scenes 또는 --all", file=sys.stderr); sys.exit(1)

    print(f"[i] 재패킹 씬 {len(scenes)}개: {scenes}")

    cmd = ['py', args.repack, '--eboot', args.eboot, '--dat', args.dat]
    # 폰트
    if args.font and Path(args.font).exists():
        cmd += ['--replace', f'{args.font_slot}:{args.font}']
        print(f"    폰트: 슬롯{args.font_slot} <- {args.font}")
    # 씬들
    for sc in scenes:
        binp = f"{args.build_dir}/{sc}_kr.bin"
        if not Path(binp).exists():
            print(f"[!] 없음: {binp} (build_scene 먼저)", file=sys.stderr); continue
        cmd += ['--replace', f'{sc}:{binp}']
    cmd += ['--out-dat', args.out_dat, '--out-eboot', args.out_eboot]

    print("  $", " ".join(cmd))
    r = subprocess.run(cmd, env=_utf8_env())
    if r.returncode != 0:
        raise SystemExit("repack 실패")
    print(f"\n[[OK]] -> {args.out_dat}, {args.out_eboot}")
    print("    CN 롬에 배치 후 PPSSPP 실행")


if __name__ == '__main__':
    main()
