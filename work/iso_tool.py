# -*- coding: utf-8 -*-
# 최소 ISO9660 리더 — PSP UMD ISO 의 파일 목록/추출용.
#   py work/iso_tool.py list <iso>
#   py work/iso_tool.py extract <iso> <경로> <출력>      (경로 예: PSP_GAME/USRDIR/DAT.BIN)
#   py work/iso_tool.py hash <iso> <경로>
import hashlib
import struct
import sys

SEC = 2048


def _records(f, lba, size):
    f.seek(lba * SEC)
    data = f.read(size)
    out, p = [], 0
    while p < len(data):
        ln = data[p]
        if ln == 0:                     # 섹터 나머지는 패딩 -> 다음 섹터로
            p = (p // SEC + 1) * SEC
            if p >= len(data):
                break
            continue
        ext = struct.unpack_from("<I", data, p + 2)[0]
        dsz = struct.unpack_from("<I", data, p + 10)[0]
        flags = data[p + 25]
        nlen = data[p + 32]
        name = data[p + 33:p + 33 + nlen]
        if nlen == 1 and name in (b"\x00", b"\x01"):
            nm = "." if name == b"\x00" else ".."
        else:
            nm = name.decode("ascii", "replace").split(";")[0]
        out.append((nm, ext, dsz, bool(flags & 2)))
        p += ln
    return out


def walk(f, lba, size, prefix=""):
    for nm, ext, dsz, isdir in _records(f, lba, size):
        if nm in (".", ".."):
            continue
        path = prefix + "/" + nm if prefix else nm
        if isdir:
            yield from walk(f, ext, dsz, path)
        else:
            yield path, ext, dsz


def root(f):
    f.seek(16 * SEC)
    pvd = f.read(SEC)
    if pvd[1:6] != b"CD001":
        raise SystemExit("[!] ISO9660 PVD 없음")
    rec = pvd[156:156 + 34]
    return struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]


def find(f, want):
    want = want.replace("\\", "/").upper()
    lba, sz = root(f)
    for path, ext, dsz in walk(f, lba, sz):
        if path.upper() == want:
            return ext, dsz
    return None, None


def main():
    mode, iso = sys.argv[1], sys.argv[2]
    with open(iso, "rb") as f:
        if mode == "list":
            lba, sz = root(f)
            for path, ext, dsz in sorted(walk(f, lba, sz)):
                print("%-44s %12d  lba=%d" % (path, dsz, ext))
            return
        ext, dsz = find(f, sys.argv[3])
        if ext is None:
            raise SystemExit("[!] 파일 없음: %s" % sys.argv[3])
        f.seek(ext * SEC)
        if mode == "hash":
            h = hashlib.md5()
            left = dsz
            while left:
                b = f.read(min(1 << 20, left))
                h.update(b)
                left -= len(b)
            print("%s  %d B  md5=%s" % (sys.argv[3], dsz, h.hexdigest()))
        else:
            with open(sys.argv[4], "wb") as o:
                left = dsz
                while left:
                    b = f.read(min(1 << 20, left))
                    o.write(b)
                    left -= len(b)
            print("[OK] %s -> %s (%d B)" % (sys.argv[3], sys.argv[4], dsz))


if __name__ == "__main__":
    main()
