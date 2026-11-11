"""Fill ko of work/trans/*.jp.json from the PSP Korean V1.3 script (psp_script.json), aligned by voice id.
Sheet voice id (last 0b 09 op before an item) = PSP voice id + 2 (id = (hi>>4)<<8 | lo).
python fill.py [--write]"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, 'E:/SOTNKR/tools')
sys.stdout.reconfigure(encoding='utf-8')
from align import groups, vid, vhex, NAMES, TR, U
from script_txt import is_junk
OPS = (0x02, 0x03, 0x11)
psp = json.load(open(os.path.join(HERE, 'psp_script.json'), encoding='utf-8'))
P = {}
for b in psp: P.setdefault(b['voice'], []).append(b)

# user's consistency rules + fixes of PSP spacing/typos
REPL = [('랄프', '트레버'), ('라나드', '라네드'), ('당신이갈곳으로', '당신이 갈 곳으로'),
        ('어째 벨몬드가', '어째서 벨몬드가'), ('드라큘라 부활 꾸미지', '드라큘라 부활을 꾸미지'),
        ('죽는편이', '죽는 편이'), ('저사람부터', '저 사람부터'), ('오랜만이군나의아들아', '오랜만이군, 나의 아들아'), ('….', '…')]
# Death speaks 하오체 (user decision); PSP uses 합니다체
DEATH = {'알카드 님이시군요.': '알카드 님이시구려.', '대체 무슨 일로 오신 겁니까?': '대체 무슨 일로 오셨소?',
         '아직도 인간의 편이십니까…': '아직도 인간의 편이시오…', '돌아오시라 청하진 않겠습니다': '돌아오시라 청하진 않겠소',
         '적어도 손을 떼 주십시오.': '적어도 손을 떼 주시오.', '어쩔 수 없군요': '어쩔 수 없구려', '일단 물러나겠습니다': '일단 물러나겠소',
         '한 번 더 숙고해 주십시오': '한 번 더 숙고해 주시오', '결국 여기까지 오셨군요…': '결국 여기까지 오셨구려…',
         '다시 말씀드리지.': '다시 말하겠소.', '부친을 위해 물러나십시오.': '부친을 위해 물러나시오.', '어쩔 수 없군요.': '어쩔 수 없구려.',
         '영혼을 받겠다!': '영혼을 받겠소!'}
DEATH_SCENES = {'NO3', 'RBO2'}
# explicit per-group text (name, sheet voice) -> lines (one per sheet line)
OVERRIDE = {
    ('BO6', '3dd3'): ['기다렸다.', ' ', '역시 너였군…', '어째서 벨몬드가', '드라큘라 부활을', '꾸미지?',
                      '너로군…', '어째서 벨몬드가', '드라큘라', '부활을 꾸미지?', ' '],
    ('CEN', '3cc4'): ['그것도,', '어쩔 수 없네…'],
    ('SEL', '4448'): ['그래.', ' '],
    ('ST0', '3558'): ['멸하라!', '이곳은 네놈이 살', '세계가 아니다', ' '],
    ('SEL', '444f'): ['미안하다.', '내 탓에', '또 아버지를…', ' ', ' '],
    ('RBO6', '4227'): ['그런가… 참', '아이러니군…', '힘을 갈구한 끝에', '잃어버린 것이', '내 패인이었다니…', ' '],
    ('DRE', '388a'): ['절대로…', '어머니 아냐', '네놈 누구냐!', '내 주박을', '깨다니', '마음에 드네.'],
}
OVERRIDE[('BO6RIC2', '3dd3')] = OVERRIDE[('BO6', '3dd3')]
OVERRIDE[('CENP', '3cc4')] = OVERRIDE[('CEN', '3cc4')]

def W(s): return sum(8 if ord(c) < 0x7f else 12 for c in s)   # as transcheck ('..' counted 16)
def NB(s):
    s = s.replace('...', '…').replace('..', '…')
    return sum(2 if (ord(c) >= 0x80 or c in '.,!?~') else 1 for c in s)
MAXW = 176

def pick(v, name):
    c = P.get(vhex(vid(v) - 2))
    if not c: return None
    return max(c, key=lambda b: (sum(l.count(' ') for l in b['lines']), b['file'] == name.lower()))

def clean(lines, name):
    out = []
    for l in lines:
        for a, b in REPL: l = l.replace(a, b)
        if name in DEATH_SCENES: l = DEATH.get(l, l)
        l = l.replace('…', '..')       # project convention ('..' is drawn as one ellipsis glyph)
        out.append(l if l.strip() else ' ')
    return out

def partition(words, brk, L):
    """Split words into exactly L lines (DP); prefer PSP's own breaks, even widths, <= MAXW."""
    n = len(words)
    if n <= L:
        return words + [' '] * (L - n), max(W(w) for w in words) > MAXW
    tgt = W(' '.join(words)) / L
    INF = float('inf')
    cost = [[INF] * (L + 1) for _ in range(n + 1)]; back = [[0] * (L + 1) for _ in range(n + 1)]
    cost[0][0] = 0
    for i in range(1, n + 1):
        for k in range(1, L + 1):
            for j in range(k - 1, i):
                if cost[j][k - 1] == INF: continue
                w = W(' '.join(words[j:i]))
                c = ((w - tgt) / 12) ** 2 + (0 if i == n or brk[i - 1] else 6) + (1e4 + w if w > MAXW else 0)
                if cost[j][k - 1] + c < cost[i][k]:
                    cost[i][k] = cost[j][k - 1] + c; back[i][k] = j
    res = []; i = n
    for k in range(L, 0, -1):
        j = back[i][k]; res.append(' '.join(words[j:i])); i = j
    res = res[::-1]
    return res, any(W(x) > MAXW for x in res)

def fit_lines(kl, L):
    if len(kl) <= L <= 4 and all(W(x) <= MAXW for x in kl):
        return kl + [' '] * (L - len(kl)), False      # keep PSP's own line breaks; box holds 4 lines
    if len(kl) == L and all(W(x) <= MAXW for x in kl):
        return kl, False
    words, brk = [], []
    for l in kl:
        ws = l.split(); words += ws; brk += [False] * (len(ws) - 1) + [True]
    if L <= 4:                     # fewest lines that fit, rest blank
        for K in range(min(len(kl), L), L):
            res, over = partition(words, brk, K)
            if not over: return res + [' '] * (L - K), False
    return partition(words, brk, L)

def split_runs(text, ens):
    """Distribute one screen line over its runs (proportional to English length, at spaces)."""
    if len(ens) == 1: return [text]
    words = text.split()
    if len(words) <= len(ens):
        return [w + ' ' for w in words[:-1]] + words[-1:] + [' '] * (len(ens) - len(words))
    tot = sum(len(e) for e in ens); full = len(' '.join(words)); out = []; wi = 0
    for r in range(len(ens)):
        left = len(ens) - r - 1
        if left == 0: out.append(' '.join(words[wi:])); break
        want = full * sum(len(x) for x in ens[:r + 1]) / tot
        take = wi + 1
        while take < len(words) - left and len(' '.join(words[:take + 1])) <= want + 1: take += 1
        out.append(' '.join(words[wi:take]) + ' '); wi = take
    return out

def junk(it, data):
    import re
    en = it['en']; off = it['off']
    if data[off - 1] in OPS and data[off - 2] not in OPS: en = en[1:]
    e = en.strip()
    if not e or re.search(r'[%_$&<>|^`{}~;=#@+]|\d[a-zA-Z]|[a-zA-Z]\d', e): return True
    if not re.search(r'[aeiouyAEIOUY]', e): return True
    if len(re.findall(r'[A-Za-z]', e)) <= 2 and not re.search(r'[.!?]', e): return True
    if not re.search(r'[a-z]{2,}', e) and not re.search(r'[.!?]', e): return True
    if re.fullmatch(r"'?[A-Z]{2,}", e): return True
    return False

def op_before(data, off):
    import re
    ps = [m.start() for m in re.finditer(rb'	', data[:off])]
    return ps[-1] if ps else -1

def fill(name, write=True):
    d, gs = groups(name)
    data = open(os.path.join(U, *d['file'].split('/')), 'rb').read()
    rep = dict(pages=0, filled=0, missing=[], overflow=[])
    for gi, g in enumerate(gs):
        v = g['voice']
        if gi == 0 and len(gs) > 1 and gs[1]['voice'] and (v is None or abs(vid(v) - vid(gs[1]['voice'])) > 16
                                                           or op_before(data, d['items'][g['items'][0]]['off']) < d.get('alt_start', 0)):
            v = vhex(vid(gs[1]['voice']) - 1)          # first page: its voice op lies outside this script
        items = [k for k in g['items'] if not junk(d['items'][k], data)]
        if not items: continue
        rep['pages'] += 1
        lines = [[]]
        for k in items:
            lines[-1].append(k)
            if d['items'][k].get('newline_after'): lines.append([])
        lines = [l for l in lines if l]
        if (name, g['voice']) in OVERRIDE:
            kl = clean(OVERRIDE[(name, g['voice'])], name)
        else:
            b = pick(v, name) if v else None
            if not b:
                rep['missing'].append('%s %s' % (g['voice'], ' '.join(d['items'][k]['en'] for k in items)[:70])); continue
            kl = clean(b['lines'], name)
        kl2, over = fit_lines(kl, len(lines))
        if over: rep['overflow'].append('%s %s' % (g['voice'], ' / '.join(kl2)))
        for ln, txt in zip(lines, kl2):
            parts = split_runs(txt, [d['items'][k]['en'] for k in ln])
            for k, p in zip(ln, parts):
                it = d['items'][k]; off = it['off']
                it['ko'] = p if p else ' '
        rep['filled'] += 1
    kos = [it for it in d['items'] if it.get('ko')]
    rep['bytes'] = (sum(NB(it['ko']) for it in kos), sum(len(it['en'].encode()) for it in kos))
    if write:
        json.dump(d, open(os.path.join(TR, name + '.jp.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return rep

if __name__ == '__main__':
    write = '--write' in sys.argv
    for name in NAMES:
        r = fill(name, write)
        print('%-8s pages %2d filled %2d bytes %d/%d%s' % (name, r['pages'], r['filled'], r['bytes'][0], r['bytes'][1],
                                                         ' OVER' if r['bytes'][0] > r['bytes'][1] else ''))
        for m in r['missing']: print('   missing', m)
        for m in r['overflow']: print('   wide', m)
