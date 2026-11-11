"""Export / import the dialogue as an editable text file.

python script_txt.py export   -> 대사집.txt (project folder)
python script_txt.py crawl    -> 오프닝자막.txt (opening crawl only)
python script_txt.py import   -> writes edited Korean back into the sheets (checks byte limits first)

Format: one entry = a header line starting with '@' (id, byte limit, English) + the Korean line below it.
Only edit the Korean lines. Blank Korean = keep the English there (junk runs are not exported)."""
import os, sys, json, re, glob
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
TR = os.path.join(ROOT, 'work', 'trans')
OUT = os.path.join(ROOT, '대사집.txt')
CRAWL_OUT = os.path.join(ROOT, '오프닝자막.txt')   # opening crawl lives in its own file

SCENE = {'ST0': '프롤로그(리히터 vs 드라큘라)', 'NO3': '성 입구 - 데스', 'NO4': '지하수로 - 뱃사공', 'NZ0': '연금술 연구소 - 마리아',
         'DAI': '예배당 - 마리아', 'LIB': '도서관 - 사서', 'CEN': '성 중심부 - 마리아', 'CENP': '성 중심부(분기) - 마리아',
         'TOP': '성 꼭대기 - 리히터/마리아', 'DRE': '역 꿈 - 서큐버스/리사', 'RCEN': '역성 중심 - 샤프트',
         'BO2': '보스 - 올록스 등', 'BO5': '보스 - 마리아/알카드', 'BO6': '보스 - 리히터(샤프트)', 'BO6RIC2': '보스 - 리히터(사본)',
         'RBO2': '역성 - 데스', 'RBO6': '최종 - 드라큘라', 'SEL': '엔딩', 'MAR': '보스 - 마리아(얼티밋)'}

def nbytes(s): return sum(1 if ord(c) < 0x80 else 2 for c in s.replace('...', '…'))

def is_junk(it):
    if it.get('ko'): return False
    en = it['en']
    if not re.search(r'[a-z]{2,}', en): return True
    if re.search(r'[%_\#$&<>|^`{}~;=]|\d[a-zA-Z]|[a-z][A-Z]{2}', en): return True     # binary / debug strings
    words = re.findall(r'[A-Za-z]+', en)
    return not any(len(w) >= 3 and re.search(r'[aeiouy]', w.lower()) for w in words) or ' ' not in en.strip() and len(en) < 8

def entries():
    """(id, cap, en, ko, setter-key)"""
    out = []
    for dub, suf in (('영어음성', '.json'), ('일본어음성', '.jp.json'), ('PSP음성', '.psp.json')):
        for fn in sorted(glob.glob(os.path.join(TR, '*' + suf))):
            bn = os.path.basename(fn)
            if bn.startswith(('DRA', 'extra_')) or bn.endswith('.k.json'): continue
            if suf == '.json' and bn.endswith(('.jp.json', '.psp.json')): continue
            name = bn[:-len(suf)]
            if name == 'ST0' and suf == '.json': continue        # ST0 PS1 dialogue lives in st0text.RUNS
            d = json.load(open(fn, encoding='utf-8'))
            if not isinstance(d, dict): continue
            for it in d['items']:
                if is_junk(it): continue
                out.append(('%s|%s|%s|%x' % (dub, name, suf, it['off']), it['cap'], it['en'], it.get('ko', ''), it.get('newline_after')))
    sys.path.insert(0, HERE)
    import st0text
    for off, en, ko in st0text.RUNS:
        out.append(('영어음성|ST0|RUNS|%x' % off, len(en), en, ko, None))
    for off, en, ko in st0text.CRAWL:
        out.append(('자막|ST0|CRAWL|%x' % off, len(en) - en.startswith(' '), en, ko, True))   # ' in his homeland.': the space is the x arg
    for name in ('SEL', 'MAR'):
        fn = os.path.join(TR, 'extra_%s.json' % name)
        if not os.path.exists(fn): continue
        for it in json.load(open(fn, encoding='utf-8'))['items']:
            if it.get('path') != 'cutscene' or is_junk(it): continue
            out.append(('영어음성|%s|extra|%x' % (name, it['off']), it['cap'], it['en'], it.get('ko', ''), None))
    return out

def export():
    lines = ['# 월하의 야상곡 얼티밋 PS1 한글 대사집',
             '# 수정 방법: "@"로 시작하는 줄 아래의 한글 줄만 고치세요. (@줄, 순서는 그대로)',
             '# @줄의 [숫자]는 그 칸에 들어갈 수 있는 최대 바이트: 한글 1자=2, 영문·숫자·공백·문장부호=1, "..."=2',
             '# 한 줄(화면 가로)은 한글 약 14자. 화면에서 같은 줄로 이어지는 칸은 "↵"가 없는 칸입니다.',
             '# 다 고치면 저에게 "대사집 반영해줘"라고 말해 주세요.', '']
    order = ['ST0', 'NO3', 'NO4', 'NZ0', 'DAI', 'LIB', 'BO5', 'BO2', 'CEN', 'CENP', 'TOP', 'BO6', 'BO6RIC2', 'MAR',
             'DRE', 'RCEN', 'RBO2', 'RBO6', 'SEL']
    dubs = ['영어음성', '일본어음성', 'PSP음성', '자막']
    ents = [e for e in entries() if not e[0].startswith('자막')]
    ents.sort(key=lambda e: (dubs.index(e[0].split('|')[0]), order.index(e[0].split('|')[1]) if e[0].split('|')[1] in order else 99))
    cur = None
    for key, cap, en, ko, nl in ents:
        dub, name = key.split('|')[:2]
        sec = (dub, name)
        if sec != cur:
            lines += ['', '=' * 60, '## %s · %s (%s)' % (dub, SCENE.get(name, name), name), '=' * 60, '']
            cur = sec
        lines.append('@%s [%d] %s%s' % (key, cap, en, '' if nl is False else ' ↵'))
        lines.append(ko)
    open(OUT, 'w', encoding='utf-8-sig').write('\n'.join(lines) + '\n')
    print('wrote', OUT, len(lines))
    if not os.path.exists(CRAWL_OUT): export_crawl()

def export_crawl():
    lines = ['# 월하의 야상곡 얼티밋 PS1 - 오프닝 자막 (게임 시작 전 아래에서 위로 올라가는 글)',
             '# 수정 방법: "@"로 시작하는 줄 아래의 한글 줄만 고치세요. (@줄, 줄 순서는 그대로)',
             '# 한글 줄 하나가 화면의 한 줄입니다 (위에서부터 차례로, 왼쪽 정렬).',
             '# [숫자]는 영어 원문 길이로 참고용입니다. 자막 전체가 한 덩어리라 줄마다 길이가 달라도 됩니다.',
             '# 한 줄은 한글 약 24자까지 화면에 들어갑니다. 비워 두면 그 줄은 빈 줄로 나옵니다.',
             '# 다 고치면 "오프닝 자막 반영해줘"라고 말해 주세요.', '']
    for key, cap, en, ko, nl in entries():
        if not key.startswith('자막'): continue
        lines.append('@%s [%d] %s' % (key, cap, en.strip()))
        lines.append(ko)
    open(CRAWL_OUT, 'w', encoding='utf-8-sig').write('\n'.join(lines) + '\n')
    print('wrote', CRAWL_OUT)

def parse():
    res = {}
    for fn in (OUT, CRAWL_OUT):
        if not os.path.exists(fn): continue
        L = open(fn, encoding='utf-8-sig').read().split('\n')
        for i, l in enumerate(L):
            if l.startswith('@'):
                key = l[1:].split(' [')[0]
                if fn == OUT and key.startswith('자막') and os.path.exists(CRAWL_OUT): continue   # crawl file wins
                cap = int(re.search(r'\[(\d+)\]', l).group(1))
                ko = L[i + 1] if i + 1 < len(L) else ''
                res[key] = (cap, ko.rstrip('\r'))
    return res

def do_import():
    new = parse(); errs = []; changed = 0
    for key, (cap, ko) in new.items():
        if ko and nbytes(ko) > cap: errs.append('%s: %d바이트 > %d  "%s"' % (key, nbytes(ko), cap, ko))
    if errs:
        print('칸 길이를 넘는 줄 %d개: 같은 장면의 남는 공간을 빌려 씁니다 (장면 전체가 넘치면 빌드에서 알려 줌)' % len(errs))
    sys.path.insert(0, HERE)
    by_file = {}
    for key, (cap, ko) in new.items():
        dub, name, kind, off = key.split('|'); by_file.setdefault((name, kind), {})[int(off, 16)] = ko
    for (name, kind), m in by_file.items():
        if kind in ('.json', '.jp.json', '.psp.json'):
            fn = os.path.join(TR, name + kind); d = json.load(open(fn, encoding='utf-8'))
            for it in d['items']:
                if it['off'] in m and it.get('ko', '') != m[it['off']]: it['ko'] = m[it['off']]; changed += 1
            json.dump(d, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        elif kind in ('RUNS', 'CRAWL'):
            p = os.path.join(HERE, 'st0text.py'); s = open(p, encoding='utf-8').read()
            import st0text
            for off, en, ko in getattr(st0text, kind):
                if off in m and m[off] != ko:
                    old = '(0x%x, %r, %r)' % (off, en, ko); new_ = '(0x%x, %r, %r)' % (off, en, m[off])
                    s2 = re.sub(r'\(0x%x, "%s", "%s"\)' % (off, re.escape(en).replace('"', '\\"'), re.escape(ko)), lambda _: '(0x%x, %s, %s)' % (off, json.dumps(en, ensure_ascii=False), json.dumps(m[off], ensure_ascii=False)), s)
                    if s2 == s: print('  st0text: 못 찾음', hex(off)); continue
                    s = s2; changed += 1
            open(p, 'w', encoding='utf-8').write(s)
        elif kind == 'extra':
            fn = os.path.join(TR, 'extra_%s.json' % name); d = json.load(open(fn, encoding='utf-8'))
            for it in d['items']:
                if it.get('path') == 'cutscene' and it['off'] in m and it.get('ko', '') != m[it['off']]:
                    it['ko'] = m[it['off']]; changed += 1
            json.dump(d, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
            print('  주의: extra_%s.json 직접 수정됨 (extragen.py 재생성 시 덮어씀)' % name)
    print('반영:', changed)
    # visual width check (box shows about 176 px per line: Hangul 12, ASCII 8)
    def w(t): return sum(8 if ord(c) < 0x80 else 12 for c in t.replace('...', '…'))
    line = ''; keys = []
    for key, cap, en, ko, nl in entries():
        if key.startswith('자막'): continue
        if keys and key.split('|')[:2] != keys[-1].split('|')[:2]: line = ''; keys = []
        line += ko or en; keys.append(key)
        if nl is not False:
            if w(line) > 176 and any(k in new and new[k][1] for k in keys) and any(ch >= '가' for ch in line):
                print('  화면 폭 초과(%dpx > 176, 잘려 보임): %s  %s' % (w(line), keys[0].split('|')[1], line))
            line = ''; keys = []

if __name__ == '__main__':
    {'export': export, 'crawl': export_crawl, 'import': do_import}[sys.argv[1]]()
