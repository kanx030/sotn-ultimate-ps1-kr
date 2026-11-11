"""Galmuri11 (OFL) bitmap font for the cutscene text box, and the cutscene-text code space.

Cutscene Korean text does not use the Korean-build font: it uses a bank of Galmuri11 glyphs (11x11, 1bpp,
16 bytes each) that the build places in free font RAM. Codes: 0x9000+i = 12px-wide glyph i,
0x9F00+j = narrow (8px) glyph j (punctuation). The bank is rebuilt every build from the text that uses it."""
import os, re

BDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'dl', 'galmuri', 'Galmuri11.bdf')
_glyphs = None
NARROW = set('.,!?~')                 # narrow (8px) Galmuri glyphs; other ASCII stays 1-byte
CELL_H = 11                             # rows stored per glyph (Hangul is 11 tall)
CELL_W = 11

def _load():
    global _glyphs
    if _glyphs is None:
        _glyphs = {}
        cur = None
        for line in open(BDF, encoding='utf-8', errors='replace'):
            if line.startswith('ENCODING'):
                cur = {'enc': int(line.split()[1])}
            elif line.startswith('BBX') and cur is not None:
                w, h, xo, yo = map(int, line.split()[1:5]); cur.update(w=w, h=h, xo=xo, yo=yo)
            elif line.startswith('DWIDTH') and cur is not None:
                cur['dw'] = int(line.split()[1])
            elif line.startswith('BITMAP') and cur is not None:
                cur['rows'] = []
            elif line.startswith('ENDCHAR') and cur is not None:
                _glyphs[cur['enc']] = cur; cur = None
            elif cur is not None and 'rows' in cur:
                cur['rows'].append(int(line.strip(), 16) if line.strip() else 0)
    return _glyphs

def bitmap(ch):
    """11 rows of 11-bit ints (bit 10 = leftmost), baseline at row 10 (row index CELL_H-1)."""
    g = _load().get(ord(ch))
    if g is None:
        raise KeyError('Galmuri11 has no glyph for %r' % ch)
    nbytes = (g['w'] + 7) // 8
    out = [0] * CELL_H
    top = (CELL_H - 1) - (g['yo'] + g['h'] - 1)          # row of the glyph's top line
    for r, v in enumerate(g['rows']):
        y = top + r
        if 0 <= y < CELL_H:
            bits = v >> (nbytes * 8 - g['w'])              # w significant bits
            x0 = g['xo']
            row = 0
            for c in range(g['w']):
                if bits & (1 << (g['w'] - 1 - c)) and 0 <= x0 + c < CELL_W:
                    row |= 1 << (CELL_W - 1 - (x0 + c))
            out[y] |= row
    return out

def pack(ch):
    """16 bytes: 121 bits row-major (11x11), MSB first."""
    bits = 0
    for row in bitmap(ch):
        bits = (bits << CELL_W) | row
    bits <<= 128 - CELL_W * CELL_H
    return bits.to_bytes(16, 'big')

class Bank:
    """Assigns codes to the glyphs used by cutscene text; call add() for every string, then build()."""
    def __init__(self):
        self.wide, self.narrow = [], []
    def add(self, s):
        for ch in s:
            if ord(ch) < 0x80 and ch not in NARROW:
                continue
            if ch == '.':
                if '…' not in self.wide: self.wide.append('…')        # '...' is drawn as one 12px glyph
            if ch in NARROW:
                if ch not in self.narrow and ch != ' ': self.narrow.append(ch)
            elif ord(ch) >= 0x80 or ch.isalnum():
                if ch not in self.wide: self.wide.append(ch)
    def code(self, ch):
        if ch in NARROW:
            return 0x9F00 + self.narrow.index(ch)
        return 0x9000 + self.wide.index(ch)
    def encode(self, s, cap=None):
        """Punctuation as Galmuri narrow glyphs when it fits in cap bytes, else as 1-byte ASCII."""
        s = s.replace('...', '…').replace('..', '…')
        if cap is None:
            return self._encode(s, set())
        # punctuation as glyphs; if too long, turn punctuation into 1-byte ASCII one by one (left to right)
        if len(self._encode(s, set())) > cap and s.rstrip()[-1:] == '.' and not s.rstrip().endswith('…'):
            s = s.rstrip()[:-1]                  # a final full stop is optional in Korean game text
        pos = [i for i, ch in enumerate(s) if ch in NARROW]
        for k in range(len(pos) + 1):
            b = self._encode(s, set(pos[:k]))
            if len(b) <= cap:
                return b
        return b
    def _encode(self, s, ascii_at):
        out = bytearray()
        for i, ch in enumerate(s):
            if ch == '…' and i in ascii_at:
                out += b'...'; continue
            if ord(ch) < 0x80 and (i in ascii_at or ch not in NARROW):
                out.append(ord(ch))                      # ASCII: engine's own 8x8 font / space (+8px)
            else:
                c = self.code(ch); out += bytes([c >> 8, c & 0xFF])
        return bytes(out)
    def blob(self):
        """wide glyphs then narrow glyphs, 16 bytes each. Returns (bytes, n_wide)."""
        return b''.join(pack(c) for c in self.wide + self.narrow), len(self.wide)
