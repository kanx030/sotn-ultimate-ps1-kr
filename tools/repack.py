"""Re-pack a cutscene script block so each text run takes exactly the bytes its Korean needs (no per-run cap).
The block keeps its start; opcodes are copied unchanged; the unused tail is filled with the no-op 0x0D.
Pointers anywhere in the file that point inside the block are moved with the bytes.
Timing: a speed opcode right before a run is scaled (Korean is shorter than English); runs that end a line get
invisible trailing spaces to make up the missing character time, as far as the block's spare bytes allow."""
import struct
BASE = 0x80180000
OPS = (0x02, 0x03, 0x11)
PAD = 0x0D

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
    # pass 1: encoded text per run (keep a leading opcode-argument byte)
    plan = []
    for off, ln, ko in runs:
        keep = b''
        if data[off - 1] in OPS and data[off - 2] not in OPS:
            keep = bytes([data[off]]); c0 = chr(data[off])
            if ko[:1] == c0: ko = ko[1:]
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
    # pointers into the block
    for o in range(0, len(data) - 3, 4):
        if start <= o < end: continue
        v = struct.unpack_from('<I', data, o)[0] - BASE
        if start < v < end and v in omap:
            struct.pack_into('<I', data, o, BASE + start + omap[v])
    return bytes(data)
