"""Static check of the cutscene scripts in a built image: for every cutscene overlay and each of its dub scripts
(PS1 / PSP / JP), walk the original and the built script with the interpreter's own opcode table and compare the
control stream (opcodes + argument bytes; nibble pointers compared by the command they point at). Text is skipped
(ASCII 1 byte, >=0x80 2 bytes, as the Korean hook reads it); 0x0D no-ops (repack filler) and 0x02 typing speed
(re-timed on purpose) are left out; 0x03 wait values may differ only in the JP-dub script (jptiming).

python scriptcheck.py ../work/build/testC12.bin            -> report every mismatch (exit 1 if any)
python scriptcheck.py --self                               -> apply transapply in memory (no image needed)

Opcode table read from the interpreter jump table (BO6 0x801A6B58, 25 entries; same in all ST0-type overlays,
NO4 has an older variant). 0x0C/0x0F/0x13: 4-byte nibble pointer ((((b0<<4|b1)<<4|b2)<<4|b3) + 0x100000 = KUSEG
address). 0x0E = switch: nibble pointer to a selector byte, then a table of nibble pointers (one per value), the
interpreter jumps to table[selector]. 0x0F = jump. These pointers must follow the bytes when a block is re-packed."""
import os, sys, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cutscene

BASE = 0x80180000
ARGS = {0x00: 0, 0x01: 0, 0x02: 1, 0x03: 1, 0x04: 0, 0x05: 2, 0x06: 0, 0x07: 2, 0x08: 0, 0x09: 2, 0x0A: 0,
        0x0B: 0, 0x0C: 4, 0x0D: 0, 0x0E: 4, 0x0F: 4, 0x10: 1, 0x11: 1, 0x12: 0, 0x13: 5, 0x14: 2, 0x15: 0,
        0x16: 1, 0x17: 0, 0x18: 1}
# NO4: 0x0C-0x0F no-ops, 0x12/0x13 portrait (5 args), 0x15-0x18 flag waits (1 arg)
ARGS_NO4 = dict(ARGS); ARGS_NO4.update({0x0C: 0, 0x0D: 0, 0x0E: 0, 0x0F: 0, 0x12: 5, 0x13: 5, 0x15: 1, 0x17: 1})
PTR_OPS = (0x0C, 0x0E, 0x0F, 0x13)

def _jt(data):
    w = lambda o: struct.unpack_from('<I', data, o)[0]
    for o in range(0, len(data) - 32, 4):
        x = w(o)
        if x >> 26 == 11 and (x & 0xFFFF) == 25:                 # sltiu v0,v1,25 ; lui at ; addu ; lw v0,lo(at)
            for q in range(o + 4, o + 24, 4):
                a = w(q)
                if a >> 26 == 15 and (a >> 16) & 31 == 1 and w(q + 8) >> 26 == 35:
                    lo = w(q + 8) & 0xFFFF
                    t = ((a & 0xFFFF) << 16) + lo - (0x10000 if lo & 0x8000 else 0) - BASE
                    if 0 <= t < len(data) - 100:
                        return [w(t + 4 * k) for k in range(25)]
    return None

_cache = {}
def arg_table(data):
    key = (len(data), bytes(data[:64]))
    if key not in _cache:
        e = _jt(data)
        _cache[key] = ARGS_NO4 if e and e[0x0C] == e[0x0D] == e[0x0E] == e[0x0F] else ARGS
    return _cache[key]

def nib(b):
    """4 script bytes -> file offset of the target, or None if not a consistent in-overlay nibble pointer."""
    if len(b) < 4 or any((b[i] & 15) != (b[i + 1] >> 4) for i in range(3)):
        return None
    v = (((((b[0] << 4) | b[1]) << 4 | b[2]) << 4) | b[3]) + 0x100000
    return v - 0x180000 if 0x180000 <= v < 0x200000 else None

def nib_enc(off):
    v = off + 0x80000                                            # file offset -> KUSEG 0x18xxxx - 0x100000
    assert 0 <= v < 0x100000, hex(off)
    return bytes([(v >> 12) & 0xFF, (v >> 8) & 0xFF, (v >> 4) & 0xFF, v & 0xFF])

def walk(data, start, stop, args=None, ptrs=None, cmds=None):
    """Linear walk -> list of (pos, op, args_bytes, ptr_targets). Text skipped. Stops at stop, a bad byte or
    an end opcode followed by zero padding. ptrs: dict that receives {pos of 4 pointer bytes: target}.
    cmds: list that receives (pos, total length) of every command (0x02/0x0D included).
    walk.bnd = set of token start positions."""
    if args is None: args = arg_table(data)
    pops = PTR_OPS if args is ARGS else ()
    out = []; i = start; bnd = set()
    while i < stop:
        bnd.add(i)
        c = data[i]
        if c >= 0x80:
            i += 2; continue
        if c >= 0x20:
            i += 1; continue
        if c not in args:
            out.append((i, 'BAD', bytes([c]), ())); break
        if c == 0x00 and i + 1 < len(data) and data[i + 1] == 0x00:
            out.append((i, 0x00, b'', ())); break            # past the last script
        n = args[c]
        a = bytes(data[i + 1:i + 1 + n]); tg = []
        if c in pops:
            tg.append(nib(a[:4]))
            if ptrs is not None and tg[0] is not None: ptrs[i + 1] = tg[0]
        j = i + 1 + n
        if c == 0x0E and c in pops:                          # switch table entries
            while j + 4 <= len(data) and nib(data[j:j + 4]) is not None and len(tg) < 32:
                t = nib(data[j:j + 4]); tg.append(t)
                if ptrs is not None: ptrs[j] = t
                a += bytes(data[j:j + 4]); j += 4
        if cmds is not None: cmds.append((i, j - i))
        if c not in (0x0D, 0x02):
            out.append((i, c, a, tuple(tg)))
        i = j
    walk.bnd = bnd
    return out

def block_starts(name):
    """Start offsets of the translated script blocks of overlay <name> (first run of each sheet/block): every
    one is a text-run start, so a command boundary in both the original and the built file."""
    import json
    tr = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'trans')
    out = {}
    for suf in ('.json', '.psp.json', '.jp.json'):
        fn = os.path.join(tr, name + suf)
        if not os.path.exists(fn): continue
        for it in json.load(open(fn, encoding='utf-8'))['items']:
            if it.get('ko'):
                k = '%s%s#%d' % (name, suf, it.get('block', 0))
                out[k] = min(out.get(k, 1 << 30), it['off'])
    fn = os.path.join(tr, 'extra_%s.json' % name)
    if os.path.exists(fn):
        offs = [it['off'] for it in json.load(open(fn, encoding='utf-8'))['items']
                if it.get('path') == 'cutscene' and it.get('ko')]
        if offs: out['extra_%s' % name] = min(offs)
    return out

def scripts(data, name=None):
    """[(dub, start, stop)] for the dub scripts the remap function names (+ translated blocks of <name> that
    those walks do not reach)."""
    ri = cutscene.remap_info(data)
    if not ri: return []
    starts = {'PS1': ri['ps1'] - BASE, 'PSP': ri['psp'] - BASE, 'JP': ri['jp'] - BASE}
    if ri['ps1_b'] != ri['ps1']: starts['PS1b'] = ri['ps1_b'] - BASE
    if name:
        cover = []
        for s in set(starts.values()):
            walk(data, s, min(len(data), s + 0x3000)); cover.append((s, max(walk.bnd)))
        for k, s in block_starts(name).items():
            if not any(a <= s <= b for a, b in cover): starts[k] = s
    allst = sorted(set(starts.values()))
    res = []
    for k, s in starts.items():
        nx = [x for x in allst if x > s]
        stop = min(nx[0] if nx else len(data), s + 0x3000, len(data))
        res.append((k, s, stop))
    return res

def script_ptrs(data, extra_starts=()):
    """All nibble pointers reachable by walking the dub scripts (+ extra start offsets): {pos: target}."""
    ptrs = {}
    for _, s, e in scripts(data):
        walk(data, s, e, ptrs=ptrs)
    for s in extra_starts:
        walk(data, s, min(len(data), s + 0x3000), ptrs=ptrs)
    return ptrs

def compare(name, orig, new, info=None):
    """-> list of problem strings. info: list that collects allowed differences (JP-dub wait re-timing)."""
    probs = []
    for k, s, stop in scripts(orig, name.split('.')[0]):
        a = walk(orig, s, stop); ba = walk.bnd
        b = walk(new, s, min(len(new), stop + 0x400)); bb = walk.bnd
        pa_list = [p[0] for p in a]; pb_list = [p[0] for p in b]
        def key(t, plist, bnd):
            if t is None: return None
            if not (s <= t < stop): return ('out', t)          # outside the script area: must be unchanged
            n = bisect.bisect_left(plist, t)
            return ('cmd', n) if t in bnd else ('mid', n, t)   # mid = not on a char/command boundary
        for n in range(len(a)):
            pa, ca, aa, ta = a[n]
            if ca == 'BAD':
                break                                   # original ran into non-script data: stop comparing
            if n >= len(b):
                probs.append('%s %s: built script ends early at command %d (orig @%x %02x)' % (name, k, n, pa, ca)); break
            pb, cb, ab, tb = b[n]
            if ca != cb or (ca not in PTR_OPS + (0x03,) and aa != ab) or (ca == 0x13 and aa[4:] != ab[4:]) \
                    or len(ta) != len(tb):
                probs.append('%s %s: cmd %d orig @%x %02x %s / built @%x %s %s  (orig ctx %s | built ctx %s)' % (
                    name, k, n, pa, ca, aa.hex(), pb, cb if cb == 'BAD' else '%02x' % cb, ab.hex(),
                    orig[max(s, pa - 12):pa + 6].hex(), new[max(s, pb - 12):pb + 6].hex()))
                break
            if ca == 0x03 and aa != ab:
                if k == 'JP':
                    if info is not None: info.append('%s %s: wait @%x %s -> %s' % (name, k, pa, aa.hex(), ab.hex()))
                else:
                    probs.append('%s %s: cmd %d wait arg changed orig @%x 03 %s / built @%x 03 %s' % (name, k, n, pa, aa.hex(), pb, ab.hex()))
            for x, y in zip(ta, tb):
                kx = key(x, pa_list, ba); ky = key(y, pb_list, bb)
                if kx != ky:
                    probs.append('%s %s: cmd %d @%x/%x %02x pointer %s %s / built %s %s' % (
                        name, k, n, pa, pb, ca, hex(x) if x is not None else None, kx,
                        hex(y) if y is not None else None, ky))
    return probs

def built_files(img_path):
    import iso, build
    im = iso.Img(img_path)
    ents = {e['path'].lstrip('/').split(';')[0]: e for e in im.walk() if not e['dir']}
    for f in build.CUTSCENE_FILES:
        e = ents.get(f)
        if e: yield f, im.read_file(e['lba'], e['size'])

def main():
    import build
    if len(sys.argv) < 2:
        print(__doc__); return
    allp = []; info = []
    if sys.argv[1] == '--self':
        import transapply
        src = []
        for f in build.CUTSCENE_FILES:
            d = build.read(os.path.join(build.U, *f.split('/')))
            if f != 'ST/ST0/ST0.BIN':
                d, _ = transapply.apply(f, d)
            src.append((f, d))
    else:
        src = list(built_files(sys.argv[1]))
    for f, new in src:
        orig = build.read(os.path.join(build.U, *f.split('/')))
        p = compare(f.split('/')[-1], orig, new, info)
        n = sum(len(walk(orig, s, e)) for _, s, e in scripts(orig, f.split('/')[-1].split('.')[0]))
        np_ = len(script_ptrs(orig))
        print('%-20s %5d commands %3d pointers  %s' % (f, n, np_, 'OK' if not p else '%d MISMATCH' % len(p)))
        allp += p
    for x in allp: print('  ' + x)
    if sys.argv[1] == '--self':
        import repack
        print('nibble pointers relocated by repack: %d' % len(repack.RELOC))
    print('JP-dub wait values re-timed (allowed): %d' % len(info))
    print('total mismatches:', len(allp))
    sys.exit(1 if allp else 0)

if __name__ == '__main__':
    main()
