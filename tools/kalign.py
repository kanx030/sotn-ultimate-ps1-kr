"""Align the Korean build's (JP-based) cutscene text with the US PS1 script by voice id (opcode 0b 09 hi lo).
Writes work/trans/<NAME>.k.json: blocks [{voice, k_text, items:[indices into <NAME>.json items]}]."""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(__file__))
import build
TR = os.path.join(build.ROOT, 'work', 'trans')
KM = {int(k, 16): v for k, v in json.load(open(os.path.join(build.ROOT, 'work', 'kmap.json'), encoding='utf-8'))['map'].items()}
FW = {0x8140: ' ', 0x8141: ',', 0x8142: '.', 0x8143: ',', 0x8144: '.', 0x8145: '·', 0x8148: '?', 0x8149: '!',
      0x815B: '-', 0x8160: '~', 0x8163: '…', 0x8169: '(', 0x816A: ')', 0x8175: '「', 0x8176: '」', 0x8168: '"'}
VOICE = re.compile(rb'\x0b\x09(..)', re.S)

def k_blocks(data):
    """voice id -> decoded Korean text of the K-build script (first occurrence)."""
    out = {}
    ms = list(VOICE.finditer(data))
    for n, m in enumerate(ms):
        vid = m.group(1).hex()
        end = ms[n + 1].start() if n + 1 < len(ms) else min(len(data), m.end() + 0x400)
        seg = data[m.end():end]
        s = ''; i = 0
        while i < len(seg):
            b = seg[i]
            if b >= 0x81 and i + 1 < len(seg):
                c = (b << 8) | seg[i + 1]
                if c in KM or c in FW:
                    s += KM.get(c) or FW[c]; i += 2; continue
                i += 1; continue
            if b == 0x01 and not s.endswith('/'): s += '/'
            i += 1
        s = s.strip('/ ')
        if s and vid not in out: out[vid] = s
    return out

def us_blocks(data, items):
    ms = [(m.start(), m.group(1).hex()) for m in VOICE.finditer(data)]
    res = []
    for k, it in enumerate(items):
        v = None
        for off, vid in ms:
            if off < it['off']: v = vid
            else: break
        if not res or res[-1]['voice'] != v:
            res.append(dict(voice=v, items=[]))
        res[-1]['items'].append(k)
    return res

def main(names):
    sys.stdout.reconfigure(encoding='utf-8')
    for name in names:
        d = json.load(open(os.path.join(TR, name + '.json'), encoding='utf-8'))
        f = d['file']
        kp = os.path.join(build.ROOT, 'work', 'K', *f.split('/'))
        if not os.path.exists(kp):
            print(name, 'no K file'); continue
        kb = k_blocks(open(kp, 'rb').read())
        ub = us_blocks(build.read(os.path.join(build.U, *f.split('/'))), d['items'])
        hit = 0
        for b in ub:
            b['k_text'] = kb.get(b['voice'], '') if b['voice'] else ''
            b['en'] = ' / '.join(d['items'][k]['en'] for k in b['items'])
            hit += bool(b['k_text'])
        json.dump(dict(file=f, blocks=ub), open(os.path.join(TR, name + '.k.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('%-8s blocks %2d, with K text %2d' % (name, len(ub), hit))

if __name__ == '__main__':
    main(sys.argv[1:] or [os.path.basename(p)[:-5] for p in sorted(os.listdir(TR)) if p.endswith('.json') and not p.endswith('.k.json') and p != 'DRA_B.json'])
