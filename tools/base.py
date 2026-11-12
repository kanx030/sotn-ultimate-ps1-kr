"""Which SOTN Ultimate release the patch is built on (one setting for every tool).

    SOTN_BASE=1.2 python build.py out.bin     # old base (reproduces the v1.0/v1.1 release)
    python build.py out.bin                   # default: newest base

Each base = the user-built image in 원본롬/ + its files extracted to work/<udir>/ (tools/extract_base.py).
Adding a version: build the image with that version's builder.html, add a line here, run
`python extract_base.py <ver>`, then build and follow the asserts (addresses are found by signature where
possible, see docs/port_v1.4.md).
"""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

BASES = {
    '1.2': dict(img='SOTN Ultimate (PS1 Version) v1.2.bin', udir='U', md5='b8b9cd07c9251919bcf02c8ebbb4602b',
                size=683034912),
    '1.4': dict(img='SOTN Ultimate (PS1 Version) v1.4.bin', udir='U14', md5='901d74656aedbd8da3050d6a3716f32f',
                size=704762688),
}
# bases recorded by ultimate_update.py (work/bases.json, keys 'v1.x') are added automatically
try:
    import json as _json
    for _tag, _d in _json.load(open(os.path.join(ROOT, 'work', 'bases.json'), encoding='utf-8')).items():
        _v = _tag.lstrip('v')
        if _v not in BASES:
            BASES[_v] = dict(img=os.path.basename(_d['image']), udir='U' + _v.replace('.', ''), md5=_d['md5'],
                             size=_d.get('size'))
except (OSError, ValueError):
    pass
VERSION = os.environ.get('SOTN_BASE', '1.4')
assert VERSION in BASES, 'SOTN_BASE must be one of %s' % sorted(BASES)
INFO = BASES[VERSION]
SRC_IMG = os.path.join(ROOT, '원본롬', INFO['img'])
U = os.path.join(ROOT, 'work', INFO['udir'])
V14 = VERSION >= '1.4'


def upath(*parts):
    """Path of an original (unpatched) file of the current base, e.g. upath('ST/LIB/LIB.BIN')."""
    out = []
    for p in parts:
        out += p.split('/')
    return os.path.join(U, *out)


def uread(*parts):
    return open(upath(*parts), 'rb').read()


def by_version(**kw):
    """by_version(v12=..., v14=...): the value for the current base (newest entry at or below it)."""
    cur = tuple(int(x) for x in VERSION.split('.'))
    ok = [k for k in kw if (int(k[1]), int(k[2:])) <= cur]
    assert ok, (kw, VERSION)
    return kw[max(ok, key=lambda k: (int(k[1]), int(k[2:])))]
