"""Re-pack a cutscene script block so each text run takes exactly the bytes its Korean needs (no per-run cap).
The block keeps its start; opcodes are copied unchanged; the unused tail is filled with the no-op 0x0D.
Pointers anywhere in the file that point inside the block are moved with the bytes.
Timing: a speed opcode right before a run is scaled (Korean is shorter than English); runs that end a line get
invisible trailing spaces to make up the missing character time, as far as the block's spare bytes allow."""
import struct, bisect
BASE = 0x80180000
OPS = (0x02, 0x03, 0x11)
PAD = 0x0D
RELOC = []          # (old ptr pos, old target, new ptr pos, new target) of every nibble pointer moved

def _scan(data, start, end, run_offs):
    """Walk the block with the interpreter opcode table -> (sorted [(pos, len)] of commands, {ptr pos: target}).
    Starts from the nearest dub-script start before the block when that walk reaches the block (so a first run
    that begins with an argument byte is seen), else from the block start; after a stop (end + padding or a byte
    that is no opcode) it restarts at the next run. Pointers of the dub scripts outside the block are included."""
    import scriptcheck as sc
    args = sc.arg_table(data)
    cmds, ptrs = [], {}
    i = start
    for _, s, _e in sorted(sc.scripts(data), key=lambda x: -x[1]):
        if start - 0x3000 <= s <= start:
            sc.walk(data, s, end, args)
            if max(sc.walk.bnd) >= start:
                i = s; break
    while i < end:
        sc.walk(data, i, end, args, ptrs, cmds)
        q = max(sc.walk.bnd)
        nxt = [o for o in run_offs if o > q]
        if not nxt: break
        i = nxt[0]
    for p, t in sc.script_ptrs(data).items():
        if not (start <= p < end): ptrs.setdefault(p, t)
    cmds = sorted(set(c for c in cmds if c[0] + c[1] > start))
    return cmds, ptrs

def chars(b):
    n = i = 0
    while i < len(b):
        i += 2 if b[i] >= 0x80 else 1; n += 1
    return n

class Overflow(Exception):
    pass

def repack(data, start, runs, encode, end=None, timing=True, prefix=None):
    """runs: list of (off, en_bytes_len, ko_str). encode(ko, en_len) -> bytes. Returns new data."""
    data = bytearray(data)
    runs = sorted(r for r in runs if r[2])
    if not runs:
        return bytes(data)
    # block = first run .. end of last run: the 0x0D filler then sits right after the last run, exactly where
    # per-run padding used to go, so every opcode keeps its arguments
    start = runs[0][0]
    if end is None:
        end = runs[-1][0] + runs[-1][1]
    # the block's control stream (interpreter opcode table): command spans + nibble pointers (0x0C/0x0E/0x0F/0x13)
    cspan, ptrs = _scan(data, start, end, [r[0] for r in runs])
    cpos = [c[0] for c in cspan]
    # pass 1: encoded text per run (keep leading bytes that are really arguments of the command before the run,
    # e.g. '03 28' wait 0x28 = '(' or '11 02 03 28': the extractor took them for text)
    plan = []
    for off, ln, ko in runs:
        keep = b''
        k = bisect.bisect_left(cpos, off) - 1
        if k >= 0 and cspan[k][0] < off < cspan[k][0] + cspan[k][1]:
            keep = bytes(data[off:min(cspan[k][0] + cspan[k][1], off + ln)])
        elif not cspan and data[off - 1] in OPS and data[off - 2] not in OPS:   # no scan: old guess
            keep = bytes([data[off]])
        if keep:
            c0 = keep.decode('latin-1')
            if ko.startswith(c0): ko = ko[len(c0):]
            ko = ko.lstrip() or ' '
        b = keep + (prefix or {}).get(off, b'') + encode(ko, 10 ** 6)   # prefix: opcodes (jptiming)
        spd = off - 1 if (data[off - 2] == 0x02 and 1 <= data[off - 1] <= 0x20 and data[off - 3] not in OPS) else None
        nxt = data[off + ln] if off + ln < len(data) else 0
        plan.append(dict(off=off, ln=ln, b=b, spd=spd, line_end=nxt in (0x00, 0x01, 0x06, 0x0A, 0x0B)))
    total_new = (end - start) + sum(len(p['b']) - p['ln'] for p in plan)
    if total_new > end - start:
        raise Overflow('block %x..%x needs %d more bytes' % (start, end, total_new - (end - start)))
    slack = (end - start) - total_new
    # pass 2: timing (speed scaling, trailing spaces from slack)
    err = 0.0
    for p in plan:
        k = max(1, chars(p['b'])); en_chars = p['ln']
        if not timing:
            continue
        if p['spd'] is not None:
            sp = data[p['spd']]
            want = sp * en_chars / k + err / k
            ns = max(1, min(0x30, int(want + 0.5))); err = (want - ns) * k
            p['newspd'] = ns
        elif p['line_end'] and slack > 0:
            sp = min(slack, max(0, en_chars - k)); p['b'] += b' ' * sp; slack -= sp
    # pass 3: rebuild
    out = bytearray(); omap = {}
    i = start; pi = 0
    while i < end:
        if pi < len(plan) and i == plan[pi]['off']:
            p = plan[pi]
            if 'newspd' in p:
                if p['spd'] < start: data[p['spd']] = p['newspd']
                else: out[len(out) - 1] = p['newspd']
            for k in range(p['ln']): omap[i + k] = len(out)
            out += p['b']; i += p['ln']; pi += 1
        else:
            omap[i] = len(out); out.append(data[i]); i += 1
    assert len(out) <= end - start
    out += bytes([PAD]) * (end - start - len(out))
    data[start:end] = out
    # nibble pointers (switch tables, jumps, end markers) that point into the block follow their target
    import scriptcheck as sc
    for p, t in sorted(ptrs.items()):
        if not (start <= t < end): continue
        if t not in omap: raise Overflow('pointer @%x -> %x not mappable' % (p, t))
        np_ = start + omap[p] if start <= p < end else p
        old = sc.nib_enc(t)
        assert bytes(data[np_:np_ + 4]) == old, (hex(p), hex(np_), data[np_:np_ + 4].hex(), old.hex())
        data[np_:np_ + 4] = sc.nib_enc(start + omap[t])
        RELOC.append((p, t, np_, start + omap[t]))
    # pointers into the block
    for o in range(0, len(data) - 3, 4):
        if start <= o < end: continue
        v = struct.unpack_from('<I', data, o)[0] - BASE
        if start < v < end and v in omap:
            struct.pack_into('<I', data, o, BASE + start + omap[v])
    _reloc_code(data, start, end, omap, set(cpos))
    return bytes(data)

CODE_RELOC = []     # (addiu va, old target va, new target va): code immediates moved with their script command

def _reloc_code(data, start, end, omap, cmd_starts):
    """Code that names a script command by address (lui rt,hi ; addiu/ori rx,rt,lo), e.g. BO2's post-fight
    script start 0x80181DC5 or 'has the script reached X' checks: move the immediate with the command.
    Only targets that are command starts inside the block; the lui half must stay the same (else: error)."""
    w = lambda a: struct.unpack_from('<I', data, a)[0]
    for a in range(0, len(data) - 4, 4):
        if start - 4 < a < end: continue
        x = w(a)
        if x >> 26 != 15: continue
        rt, hi = (x >> 16) & 31, x & 0xFFFF
        if not 0x8018 <= hi <= 0x801C: continue
        for b in range(a + 4, min(len(data) - 4, a + 48), 4):
            if start - 4 < b < end: break
            y = w(b)
            op = y >> 26
            if op in (9, 13) and (y >> 21) & 31 == rt:
                lo = y & 0xFFFF
                va = (hi << 16) + (lo - 0x10000 if op == 9 and lo & 0x8000 else lo)
                t = va - BASE
                if start < t < end and t in cmd_starts and t in omap and omap[t] != t - start:
                    nva = BASE + start + omap[t]
                    nhi = (nva + (0x8000 if op == 9 else 0)) >> 16
                    if nhi != hi:
                        raise Overflow('code @%x -> %x: new target %x needs another lui' % (BASE + b, va, nva))
                    struct.pack_into('<I', data, b, (y & 0xFFFF0000) | (nva & 0xFFFF))
                    CODE_RELOC.append((BASE + b, va, nva))
                break
            if op in (15, 9, 13, 35, 33, 32, 36, 37) and (y >> 16) & 31 == rt:
                break                                   # rt overwritten
