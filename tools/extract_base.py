"""Extract every file of a base image to work/<udir>/ (see base.py).  python extract_base.py [version]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) > 1:
    os.environ['SOTN_BASE'] = sys.argv[1]
import iso, base

im = iso.Img(base.SRC_IMG)
for e in im.walk():
    p = os.path.join(base.U, *e['path'].lstrip('/').split(';')[0].split('/'))
    if e['dir']:
        os.makedirs(p, exist_ok=True); continue
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:           # form-1 user data (XA streams come out as their first 2048 bytes/sector)
        n = (e['size'] + 2047) // 2048
        for i in range(0, n, 4096):
            f.write(im.data(e['lba'] + i, min(4096, n - i)))
        f.truncate(e['size'])
print('extracted', base.SRC_IMG, '->', base.U)
