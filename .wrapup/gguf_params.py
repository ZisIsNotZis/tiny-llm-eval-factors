#!/usr/bin/env python3
"""Read true parameter count from a GGUF header (sum of tensor elements).

bpw = 8 * file_size_bytes / n_params.  The DB's __size column is unreliable
(GLM-4.7-Flash reports 23.78 for Q2 and 27.56 for Q3 of the same model), so the
bpw axis in RESULTS_BY_BENCHMARK.md is derived from this instead.
"""
import struct
import sys


def _rstr(f):
    n = struct.unpack('<Q', f.read(8))[0]
    return f.read(n).decode('utf-8', 'replace')


def _rval(f, t):
    simple = {0: '<B', 1: '<b', 2: '<H', 3: '<h', 4: '<I', 5: '<i',
              6: '<f', 7: '<B', 10: '<Q', 11: '<q', 12: '<d'}
    if t in simple:
        return struct.unpack(simple[t], f.read(struct.calcsize(simple[t])))[0]
    if t == 8:
        return _rstr(f)
    if t == 9:
        et = struct.unpack('<I', f.read(4))[0]
        cnt = struct.unpack('<Q', f.read(8))[0]
        for _ in range(cnt):
            _rval(f, et)
        return None
    raise ValueError("bad gguf value type %r" % t)


def gguf_params(path, want=()):
    with open(path, 'rb') as f:
        if f.read(4) != b'GGUF':
            raise ValueError("not a gguf: %s" % path)
        f.read(4)                                   # version
        n_tensors = struct.unpack('<Q', f.read(8))[0]
        n_kv = struct.unpack('<Q', f.read(8))[0]
        meta = {}
        for _ in range(n_kv):
            k = _rstr(f)
            t = struct.unpack('<I', f.read(4))[0]
            v = _rval(f, t)
            if k in want:
                meta[k] = v
        total = 0
        for _ in range(n_tensors):
            _rstr(f)                                # tensor name
            nd = struct.unpack('<I', f.read(4))[0]
            dims = [struct.unpack('<Q', f.read(8))[0] for _ in range(nd)]
            f.read(4)                               # ggml type
            f.read(8)                               # offset
            p = 1
            for d in dims:
                p *= d
            total += p
        return total, meta


if __name__ == '__main__':
    import os
    for p in sys.argv[1:]:
        try:
            n, meta = gguf_params(p, want=('general.architecture',))
            sz = os.path.getsize(p)
            print(f"{os.path.basename(p)}\t{n}\t{sz}\t{8.0*sz/n:.3f}\t{meta.get('general.architecture','')}")
        except Exception as e:                      # noqa: BLE001
            print(f"{os.path.basename(p)}\tERROR\t{e}")
