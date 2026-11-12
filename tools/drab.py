"""Engine B text of US DRA.BIN (strings drawn by DrawTextToVram 0x800F7800 through the
16x15 glyph API): equipment / accessory / relic / spell descriptions, relic names, spell
names, system help, the button-assign line and the memory-card / save messages.

  python drab.py extract   -> work/trans/DRA_B.json  (keeps existing 'ko' by id)
  python drab.py check     -> width / charset report, new syllables (not in kmap.json)

Engine B facts (see work/dra_text_report.md and the code at 0x800F7800):
  * NUL-terminated. a-z -> 0x8281+, A-Z -> 0x8260+, ' ' -> 0x8140 (+2 bytes gap);
    every other byte is the high byte of a 2-byte code. 0x8168 (”) skips the next
    2 bytes (US uses ””word”” for one quote) -> never emit 0x8168 in Korean.
  * Proportional: each 12x16 glyph (16 px squeezed to 12) is trimmed to its used
    byte columns (2 px each), +1 byte gap if narrower than 6 bytes; space = 6 px.
  * Buffer width: a2=0 -> 0x90 bytes = 288 px, a2=1 -> 0x3C bytes = 120 px; text past
    the width is cut (not overflow).
  * Spell descriptions are also sent to the 2-byte-only renderer 0x800F76F4 (0x800FAD1C),
    so they are encoded with 2-byte codes only (no 1-byte letters / spaces).

JSON entry: id, cat, idx (table indices sharing the string), va, len (bytes incl. NUL),
en, refs (file offsets of 32-bit data pointers), code_refs ([lui_off, lo_off] pairs that
build the address), limit (px), en_px, ko, px (Korean estimate), ko_len (bytes incl. NUL).
"""
import json, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kmap

ROOT = kmap.ROOT
WORK = kmap.WORK
DRA = __import__('base').upath('DRA.BIN')
OUT = os.path.join(WORK, 'trans', 'DRA_B.json')
FONTEXT = os.path.join(WORK, 'fontext.json')
BASE = 0x800A0000

from addrmap import dra as _R                  # v1.2 addresses -> current base (signature-checked)
EQUIP, EQUIP_N, EQUIP_S = _R(0x800A499C), 228, 0x34
ACC, ACC_N, ACC_S = _R(0x800A77EC), 93, 0x20
RELIC, RELIC_N, RELIC_S = _R(0x800DFC28), 31, 0x10
SPELL, SPELL_N, SPELL_S = _R(0x800DF780), 8, 0x1C
SYSHELP, SYSHELP_N = _R(0x800A2B04), 7
BUTTON = _R(0x800DC11C)
SAVE_LO, SAVE_HI = _R(0x800DC694), _R(0x800DC7E4)      # Data saved... "  No  "
EMPTY = _R(0x800DC800)                             # "" used by unused table entries

LIMIT = {'equip_desc': 288, 'acc_desc': 288, 'relic_desc': 288, 'spell_desc': 288,
         'sys_help': 288, 'button': 288, 'relic_name': 120,
         # spell names render into a 288 px buffer; 144 = longest US name (Dark Metamorphosis)
         'spell_name': 144,
         # save dialog: buffer is 288 px (0x800F7B88 passes a2=0) but the box is small;
         # 126 = longest US line ("  Select the slot.")
         'save_msg': 126}
TWO_BYTE_ONLY = {'spell_desc'}

# ------------------------------------------------------------------ binary helpers
_D = None
def dra():
    global _D
    if _D is None:
        _D = open(DRA, 'rb').read()
    return _D

def w32(o):
    return struct.unpack_from('<I', dra(), o)[0]

def cstr(va):
    d = dra()
    o = va - BASE
    e = d.index(b'\0', o)
    return d[o:e]

def dec_raw(b):
    """English source: show 2-byte codes as their cp932 full-width chars."""
    out, i = [], 0
    while i < len(b):
        x = b[i]
        if chr(x).isalpha() and x < 0x80 or x == 0x20:
            out.append(chr(x)); i += 1
        else:
            try:
                out.append(b[i:i + 2].decode('cp932'))
            except UnicodeDecodeError:
                out.append('{%02x%02x}' % (b[i], b[i + 1]))
            i += 2
    return ''.join(out)

# ------------------------------------------------------------------ references
_WORDS = None
def data_refs(va):
    global _WORDS
    if _WORDS is None:
        d = dra()
        _WORDS = {}
        for o in range(0, len(d) - 3, 4):
            v = struct.unpack_from('<I', d, o)[0]
            if 0x800DB000 <= v < 0x800E1000:
                _WORDS.setdefault(v, []).append(o)
    return list(_WORDS.get(va, []))

_PAIRS = None
def code_refs(va):
    """lui rt,hi ... addiu/ori rX,rt,lo (within 12 insns) building va."""
    global _PAIRS
    if _PAIRS is None:
        d = dra()
        _PAIRS = {}
        for o in range(0x40000, len(d) - 4, 4):
            x = struct.unpack_from('<I', d, o)[0]
            if x >> 26 != 15:
                continue
            rt = (x >> 16) & 31
            hi = (x & 0xFFFF) << 16
            for k in range(1, 12):
                p = o + 4 * k
                if p >= len(d):
                    break
                y = struct.unpack_from('<I', d, p)[0]
                op, rs, rt2 = y >> 26, (y >> 21) & 31, (y >> 16) & 31
                if op == 9 and rs == rt:
                    imm = y & 0xFFFF
                    imm -= 0x10000 if imm & 0x8000 else 0
                    _PAIRS.setdefault((hi + imm) & 0xFFFFFFFF, []).append([o, p])
                    if rt2 == rt:
                        break
                elif op == 13 and rs == rt:
                    _PAIRS.setdefault(hi | (y & 0xFFFF), []).append([o, p])
                    if rt2 == rt:
                        break
                if (op == 15 and rt2 == rt) or op in (2, 3) or (op == 0 and (y & 0x3F) == 8):
                    break
    return list(_PAIRS.get(va, []))

# ------------------------------------------------------------------ string list
def collect():
    items = {}        # (cat, va) -> entry
    order = []

    def add(cat, va, idx):
        if va == EMPTY or not (BASE <= va < BASE + len(dra())):
            return
        k = (cat, va)
        if k not in items:
            items[k] = {'cat': cat, 'va': va, 'idx': []}
            order.append(k)
        items[k]['idx'].append(idx)

    for i in range(EQUIP_N):
        add('equip_desc', w32(EQUIP - BASE + i * EQUIP_S + 4), i)
    for i in range(ACC_N):
        add('acc_desc', w32(ACC - BASE + i * ACC_S + 4), i)
    for i in range(RELIC_N):
        add('relic_name', w32(RELIC - BASE + i * RELIC_S), i)
    for i in range(RELIC_N):
        add('relic_desc', w32(RELIC - BASE + i * RELIC_S + 4), i)
    for i in range(SPELL_N):
        add('spell_name', w32(SPELL - BASE + i * SPELL_S), i)
    for i in range(SPELL_N):
        add('spell_desc', w32(SPELL - BASE + i * SPELL_S + 8), i)
    for i in range(SYSHELP_N):
        add('sys_help', w32(SYSHELP - BASE + i * 4), i)
    add('button', BUTTON, 0)
    d = dra()
    va = SAVE_LO
    n = 0
    while va < SAVE_HI:
        s = cstr(va)
        if s:
            add('save_msg', va, n)
            n += 1
            va += len(s) + 1
        else:
            va += 1
    out = []
    count = {}
    for k in order:
        e = items[k]
        cat = e['cat']
        count[cat] = count.get(cat, 0)
        raw = cstr(e['va'])
        out.append({
            'id': '%s_%03d' % (cat, e['idx'][0]),
            'cat': cat,
            'idx': e['idx'],
            'va': '0x%08X' % e['va'],
            'len': len(raw) + 1,
            'en': dec_raw(raw),
            'refs': data_refs(e['va']),
            'code_refs': code_refs(e['va']),
            'limit': LIMIT[cat],
            'en_px': px_bytes(raw),
            'ko': '',
        })
    return out

# ------------------------------------------------------------------ width model
_FONT = None
def font():
    global _FONT
    if _FONT is None:
        _FONT = kmap.load_font().astype(bool)
    return _FONT

def glyph_px(code):
    """Advance in px of a 2-byte code in engine B (squeeze 16->12, trim, gap)."""
    if code == 0x8140:
        return 6
    idx = kmap.code_to_index(code)
    if idx is None or idx >= len(font()) or not font()[idx].any():
        return 12                                  # extension / unknown: full width
    cols = font()[idx].any(0).nonzero()[0]
    l12 = (int(cols[0]) * 3) // 4
    r12 = min(11, (int(cols[-1]) * 3 + 2) // 4)
    r = r12 - 2 * (l12 // 2)                        # after left trim by whole bytes
    a3 = r // 2 + (r & 1)
    if a3 < 6:
        a3 += 1
    return 2 * a3

def px_bytes(b):
    px, i = 0, 0
    while i < len(b):
        x = b[i]
        if 0x61 <= x <= 0x7A:
            px += glyph_px(0x8220 + x); i += 1
        elif 0x41 <= x <= 0x5A:
            px += glyph_px(0x821F + x); i += 1
        elif x == 0x20:
            px += 6; i += 1
        else:
            c = (x << 8) | b[i + 1]
            i += 2
            if c == 0x8168:
                i += 2
            px += glyph_px(c)
    return px

# ------------------------------------------------------------------ Korean encoder
SYMBOLS = set('．，！？：；～ー（）「」『』・＋－／％…→×★♪、。［］’　０１２３４５６７８９')
ASCII_FW = {c: chr(ord(c) + 0xFEE0) for c in '0123456789.,!?:;()+-/%[]'}
ASCII_FW.update({'~': '～', "'": '’'})

def _ext():
    return json.load(open(FONTEXT, encoding='utf-8')) if os.path.exists(FONTEXT) else {}

def encode(s, two_byte=False, strict=True):
    """Korean string -> engine B bytes (no NUL). Returns (bytes, problems, new_syllables)."""
    enc = kmap._load_map()[0]
    ext = _ext()
    out = bytearray()
    bad, new = [], []
    for ch in s:
        ch = ASCII_FW.get(ch, ch)
        if ('a' <= ch <= 'z' or 'A' <= ch <= 'Z'):
            if two_byte:
                c = (0x8220 if ch >= 'a' else 0x821F) + ord(ch)
                out += bytes([c >> 8, c & 0xFF])
            else:
                out.append(ord(ch))
            continue
        if ch == ' ':
            out += b'\x81\x40' if two_byte else b' '
            continue
        if '가' <= ch <= '힣':
            if ch in enc:
                c = enc[ch]
            else:
                new.append(ch)
                c = int(ext[ch], 16) if ch in ext else 0x819A   # placeholder ★ until allocated
            out += bytes([c >> 8, c & 0xFF])
            continue
        if ch in SYMBOLS:
            c = 0x8140 if ch == '　' else int.from_bytes(ch.encode('cp932'), 'big')
            out += bytes([c >> 8, c & 0xFF])
            continue
        bad.append(ch)
    return bytes(out), bad, new

def ko_px(s, cat):
    b, _, _ = encode(s, cat in TWO_BYTE_ONLY)
    return px_bytes(b)

# ------------------------------------------------------------------ commands
def load():
    return json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else []

def save(items):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)

def update_px(items):
    for e in items:
        if e.get('ko'):
            b, _, _ = encode(e['ko'], e['cat'] in TWO_BYTE_ONLY)
            e['px'] = px_bytes(b)
            e['ko_len'] = len(b) + 1
        else:
            e['px'] = None
            e['ko_len'] = None

def cmd_extract():
    old = {e['id']: e.get('ko', '') for e in load()}
    items = collect()
    for e in items:
        e['ko'] = old.get(e['id'], '')
    update_px(items)
    save(items)
    cats = {}
    for e in items:
        cats[e['cat']] = cats.get(e['cat'], 0) + 1
    print('%d strings -> %s' % (len(items), OUT))
    for c, n in cats.items():
        print('  %-11s %d' % (c, n))
    noref = [e['id'] for e in items if not e['refs'] and not e['code_refs']]
    if noref:
        print('without refs:', noref)

def cmd_check():
    items = load()
    update_px(items)
    save(items)
    enc = kmap._load_map()[0]
    ext = _ext()
    errs = 0
    new = {}
    stats = {}
    for e in items:
        st = stats.setdefault(e['cat'], [0, 0, 0, 0])
        st[0] += 1
        st[2] += e['len']
        if not e['ko']:
            print('EMPTY  %s %r' % (e['id'], e['en'])); errs += 1; continue
        st[1] += 1
        b, bad, nw = encode(e['ko'], e['cat'] in TWO_BYTE_ONLY)
        st[3] += len(b) + 1
        for ch in nw:
            new.setdefault(ch, []).append(e['id'])
        if bad:
            print('CHARS  %s %r: %r' % (e['id'], e['ko'], bad)); errs += 1
        if e['px'] > e['limit']:
            print('WIDTH  %s %d>%d %r' % (e['id'], e['px'], e['limit'], e['ko'])); errs += 1
        if e['ko'] != e['ko'].strip(' ') and e['cat'] not in ('relic_name', 'save_msg'):
            print('SPACE  %s %r' % (e['id'], e['ko']))
    print('\n%-11s %5s %5s %8s %8s' % ('cat', 'n', 'done', 'en_B', 'ko_B'))
    tot = [0, 0, 0, 0]
    for c, st in stats.items():
        print('%-11s %5d %5d %8d %8d' % (c, *st))
        tot = [a + b for a, b in zip(tot, st)]
    print('%-11s %5d %5d %8d %8d' % ('total', *tot))
    inext = [c for c in new if c in ext]
    print('\nsyllables not in kmap.json: %d (%d already in fontext.json)' % (len(new), len(inext)))
    print(''.join(sorted(new)))
    print('\n%d problem(s)' % errs)
    return errs

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'extract':
        cmd_extract()
    elif cmd == 'check':
        sys.exit(1 if cmd_check() else 0)
    else:
        print(__doc__)
