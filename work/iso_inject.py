# -*- coding: utf-8 -*-
# ISO9660 내 파일을 '같은 크기'로 제자리 교체.
#   크기 불변이 전제 (LBA/디렉터리 레코드 손대지 않음 -> 구조 안전).
#   사용: py work/iso_inject.py <iso> <ISO내경로> <넣을파일>
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iso_tool import find, SEC


def main():
    iso, want, src = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(iso, "rb") as f:
        ext, dsz = find(f, want)
    if ext is None:
        raise SystemExit("[!] ISO 안에 없음: %s" % want)
    new = open(src, "rb").read()
    if len(new) != dsz:
        raise SystemExit("[!] 크기 불일치: ISO %d B vs 새파일 %d B (제자리 교체 불가)"
                         % (dsz, len(new)))
    with open(iso, "r+b") as f:
        f.seek(ext * SEC)
        f.write(new)
    print("[OK] %s 교체 (lba=%d, %d B, md5=%s)"
          % (want, ext, dsz, hashlib.md5(new).hexdigest()))


if __name__ == "__main__":
    main()
