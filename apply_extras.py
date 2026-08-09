#!/usr/bin/env python3
# build_dat 산출물(DAT_cn_new.BIN)에 '스토리 밖' 번역 패치를 일괄 적용.
#  - battle help (슬롯 15900) : work/battle/_patch.py
#  - 이름 테이블 (슬롯 2)      : work/names/_patch.py
# 사용: py build_dat.py --all --font 00014_hangul_full.bin  후  py apply_extras.py
import subprocess, sys, os

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
STEPS = [
    ('battle help', ['work/battle/_patch.py', '--apply', '--inplace']),
    ('이름 테이블(DAT슬롯2)', ['work/names/_patch.py', '--apply']),
    ('이름 테이블(EBOOT-화자명)', ['work/names/_patch_eboot.py', '--apply']),
    ('battle help(EBOOT-표시용)', ['work/battle/_patch_eboot_bh.py', '--apply']),
]
for name, args in STEPS:
    print(f'== {name} 패치 ==')
    r = subprocess.run([sys.executable] + args, env=os.environ)
    if r.returncode != 0:
        print(f'[!] {name} 실패'); sys.exit(1)
print('[OK] extras 패치 완료 -> DAT_cn_new.BIN')
