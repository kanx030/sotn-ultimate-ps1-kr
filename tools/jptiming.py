"""Typing timing for the JP-dub scripts (*.jp.json) taken from the PSP Korean V1.3 script.

The PS1 JP-dub block (Ultimate's PSP-B script) keeps the English typing values (speed 02 xx, waits 03 xx between
lines) tuned for long English lines; the Korean lines are about half as long, so the text ran ahead of the
Japanese voice (page starts are fine: every page ends with 0a = wait for the voice).
The PSP Korean script (work/pspk/x/PS.ELF, psp_script.json, same opcodes) is timed for the Japanese voice and
the Korean text, so per page (voice id, PSP id + 2) we rebuild its schedule:
    every typed character costs the current speed, 03 xx adds xx, other ops cost nothing,
and map our lines onto it proportionally by character position (our lines are a re-split of the PSP text).
Each of our lines gets   speed = PSP time spent on its characters / its characters
                          wait before it = PSP gap before its first character (what is left after rounding)
and the page's final wait (03 xx after the last line) = PSP's final wait.
Speeds/waits are written into existing opcode arguments where the line already has one (02 xx after the voice
op, 03 xx after a newline); a line without a speed slot gets a 2-byte '02 xx' prefix inside its run (repack
packs it with the text). plan() is called by transapply for .jp.json before repack.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
PSPK = os.path.join(HERE, '..', 'work', 'pspk')
OPS = (0x02, 0x03, 0x11)
# PSP pages are text-timed (typing spans the whole voice line, page turns right after), while the PS1 page waits
# for the voice to end (0a) after typing + final wait. Measured on PS1 (ST0 prologue): 1 unit = 1 frame, the PSP
# typing of a page is as long as the voice itself (ST0 3559: 817 frames, voice page 788). So the schedule is
# compressed a little and the final wait kept short, so typing ends just before the voice does and the page
# turn stays on the voice.
SCALE = 0.8          # x ~1.07 (PS1 types ~56 chars-frames/s, measured) = ~0.86 of the PSP pace
FINAL_MAX = 16
ARGS = {0x02: 1, 0x03: 1, 0x11: 1, 0x10: 1, 0x05: 2, 0x09: 2, 0x07: 1, 0x08: 1, 0x16: 1, 0x0b: 0}
REPORT = []
_P = None


def _psp():
    global _P
    if _P is None:
        sys.path.insert(0, PSPK)
        import fill                                     # noqa (import-safe; gives pick/groups/junk)
        elf = open(os.path.join(PSPK, 'x', 'PS.ELF'), 'rb').read()
        _P = (fill, elf)
    return _P


def psp_schedule(elf, off, speed0):
    """Times (in script units) of each typed char of the PSP page starting at the voice op at `off`.
    Returns (char_times, speeds, type_end, final_wait, last_speed)."""
    i = off
    # skip the voice op: [0b] 09 hi lo [0a]
    while i < off + 8 and elf[i] != 0x09: i += 1
    i += 3
    if elf[i] == 0x0a: i += 1
    t = 0; sp = speed0; ts = []; sps = []; final = 0; seen = False
    n = len(elf)
    while i < n:
        b = elf[i]
        if b == 0x06 or b == 0x00:
            break
        if b >= 0x80:
            ts.append(t); sps.append(sp); t += sp; i += 2; final = 0; seen = True
        elif b >= 0x20 or b == 0x04:
            ts.append(t); sps.append(sp); t += sp; i += 1; final = 0; seen = True
        elif b == 0x02:
            sp = elf[i + 1]; i += 2
        elif b == 0x03:
            t += elf[i + 1]; final += elf[i + 1] if seen else 0; i += 2
        elif b == 0x0b and i + 1 < n and elf[i + 1] == 0x09:
            break                                       # next voice op (page without 06)
        else:
            i += 1 + ARGS.get(b, 0)
    type_end = t - final
    return (ts, sps), type_end, final, sp


def _psp_page_index(fill, elf):
    """voice -> list of (file, off) with the speed in force at the start of each PSP block (file order)."""
    js = json.load(open(os.path.join(PSPK, 'psp_script.json'), encoding='utf-8'))
    js.sort(key=lambda b: b['off'])
    sp = 2; out = {}
    for b in js:
        ts, te, fw, last = psp_schedule(elf, b['off'], sp)
        out[(b['voice'], b['off'])] = (ts, te, fw, sp)
        sp = last
    return out


_IDX = None


def plan(name, data, d, encode):
    """d: the .jp.json dict. Returns (edits {pos: byte}, prefix {off: bytes}). data = file bytes (before repack)."""
    global _IDX
    fill, elf = _psp()
    if _IDX is None:
        _IDX = _psp_page_index(fill, elf)
    from repack import chars
    _, gs = fill.groups(name)
    items = d['items']
    edits, prefix = {}, {}
    for gi, g in enumerate(gs):
        v = g['voice']
        if gi == 0 and len(gs) > 1 and gs[1]['voice'] and (v is None or abs(fill.vid(v) - fill.vid(gs[1]['voice'])) > 16
                                                           or fill.op_before(data, items[g['items'][0]]['off']) < d.get('alt_start', 0)):
            v = fill.vhex(fill.vid(gs[1]['voice']) - 1)
        if not v:
            continue
        b = fill.pick(v, name)
        if not b:
            continue
        key = (b['voice'], b['off'])
        if key not in _IDX:
            continue
        (ts, sps), te, fw, _ = _IDX[key]
        ks = [k for k in g['items'] if items[k].get('ko')]
        if not ks or not ts:
            continue
        # our characters per item (blank ' ' items carry no text)
        cnt = []
        for k in ks:
            ko = items[k]['ko']
            cnt.append(0 if not ko.strip() else chars(encode(ko, 10 ** 6)))
        N = sum(cnt); M = len(ts)
        if N == 0:
            continue

        def span(j, c):                                 # PSP chars covered by our chars j..j+c-1
            a = min(M - 1, int(j * M / N))
            b = max(a, min(M - 1, -(-(j + c) * M // N) - 1))
            return a, b
        j = 0; cur_t = 0.0; cur_sp = None; page_rep = []
        for idx, (k, c) in enumerate(zip(ks, cnt)):
            it = items[k]; off = it['off']
            prev = items[k - 1] if k > 0 else None
            # slots in the bytes right before this run
            gap = bytes.fromhex(prev['gap']) if prev and prev.get('gap') else b''
            sp_pos = wt_pos = None
            if data[off - 1] in OPS and data[off - 2] not in OPS:      # text starts with the op's argument
                if data[off - 1] == 0x02: sp_pos = off
                elif data[off - 1] == 0x03: wt_pos = off
            else:
                if data[off - 2] == 0x02 and data[off - 3] not in OPS: sp_pos = off - 1
                if data[off - 2] == 0x03 and data[off - 3] not in OPS: wt_pos = off - 1
                if sp_pos and data[off - 4] == 0x03 and data[off - 5] not in OPS: wt_pos = off - 3
                if wt_pos == off - 1 and data[off - 4] == 0x02 and data[off - 5] not in OPS: sp_pos = off - 3
            if c == 0:
                if wt_pos is not None and idx > 0: edits[wt_pos] = 1
                if sp_pos is not None: edits[sp_pos] = cur_sp or 1
                continue
            a, bb = span(j, c)
            start = ts[a] * SCALE
            sp = max(1, min(0x30, int(round(SCALE * sum(sps[a:bb + 1]) / c))))
            wait = start - cur_t if idx > 0 else 0
            w = max(0, min(255, int(round(wait))))
            if idx > 0 and wt_pos is not None:
                edits[wt_pos] = max(1, w)
                cur_t += max(1, w)
            elif idx > 0 and w > 2 and it.get('ko') and prev and prev.get('newline_after'):
                prefix[off] = prefix.get(off, b'') + bytes([0x03, w]); cur_t += w
            if sp_pos is not None:
                edits[sp_pos] = sp
            elif sp != cur_sp:
                prefix[off] = prefix.get(off, b'') + bytes([0x02, sp])
            cur_sp = sp
            cur_t += sp * c
            j += c
            page_rep.append((c, sp, w))
        # final wait after the last item of the page
        last = items[ks[-1]]
        e = last['off'] + len(last['en'].encode())
        if data[e] == 0x03 and fw:
            edits[e + 1] = max(1, min(FINAL_MAX, int(round(fw + (te * SCALE - cur_t)))))
        REPORT.append((name, g['voice'], b['voice'], round(te * SCALE), round(cur_t), page_rep))
    return edits, prefix


if __name__ == '__main__':
    import build
    enc = build.bank().encode
    for nm in sys.argv[1:] or ['ST0']:
        d = json.load(open(os.path.join(HERE, '..', 'work', 'trans', nm + '.jp.json'), encoding='utf-8'))
        data = open(__import__('base').upath(d['file']), 'rb').read()
        e, p = plan(nm, data, d, enc)
        print(nm, 'edits', len(e), 'prefix bytes', sum(len(x) for x in p.values()))
    for r in REPORT:
        print(r)
