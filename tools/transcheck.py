"""Check a translation sheet work/trans/<NAME>.json: byte length per run (<= cap), visual line width
(Hangul/full-width 16px, ASCII 8px, max 176px per line; a line ends at a run with newline_after), and list
syllables not in the base font (they get generated glyphs; keep them few). Does NOT allocate glyphs.
python transcheck.py NAME [NAME...]"""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
base = set(json.load(open(os.path.join(ROOT, 'kmap.json'), encoding='utf-8'))['map'].values())
ext = set(json.load(open(os.path.join(ROOT, 'fontext.json'), encoding='utf-8')))
FW = set('．？！”（）　１')
def nbytes(s): return sum(1 if ord(c) < 0x7f else 2 for c in s)
def width(s): return sum(8 if ord(c) < 0x7f else 12 for c in s)   # Galmuri11: Hangul 12px, ASCII 8px
for name in sys.argv[1:]:
    d = json.load(open(os.path.join(ROOT, 'trans', name + '.json'), encoding='utf-8'))
    errs = []; new = set(); line = ''; done = 0
    for it in d['items']:
        ko = it.get('ko', '')
        if ko:
            done += 1
            if nbytes(ko) > it['cap']: errs.append('%x too long %d>%d: %s' % (it['off'], nbytes(ko), it['cap'], ko))
            for c in ko:
                if '가' <= c <= '힣' and c not in base: new.add(c)
                elif ord(c) >= 0x7f and not ('가' <= c <= '힣') and c not in FW: errs.append('%x bad char %r' % (it['off'], c))
        line += ko if ko else it['en']
        if it.get('newline_after'):
            if width(line) > 176: errs.append('%x line too wide %dpx: %s' % (it['off'], width(line), line))
            line = ''
    print('%s: %d/%d translated, %d errors, new glyphs (%d): %s' % (name, done, len(d['items']), len(errs), len(new - ext), ''.join(sorted(new - ext))))
    for e in errs: print('  ', e)
