"""List files with English sentence-like text and whether they have a translation sheet."""
import glob, os, re, json, sys
sys.stdout.reconfigure(encoding='utf-8')
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
done = set()
for fn in glob.glob(os.path.join(W, 'trans', '*.json')):
    bn = os.path.basename(fn)
    if bn.startswith('DRA') or bn.endswith('.k.json'): continue
    d = json.load(open(fn, encoding='utf-8'))
    if isinstance(d, dict): done.add(d['file'])
for f in sorted(glob.glob(os.path.join(W, 'U', '**', '*.BIN'), recursive=True)):
    rel = os.path.relpath(f, os.path.join(W, 'U')).replace(os.sep, '/')
    x = open(f, 'rb').read()
    runs = [m.group() for m in re.finditer(rb"[A-Za-z][A-Za-z ,.'!?\-]{9,}", x) if re.search(rb'[a-z]{3} [a-z]{2,}', m.group())]
    if len(runs) >= 3:
        print('%-22s %4d %-5s %s' % (rel, len(runs), rel in done, ' | '.join(r[:28].decode() for r in runs[:3])))
