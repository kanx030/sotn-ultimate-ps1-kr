"""Run a move plan then snapshot every <iv> s for <secs> s; drop near-duplicate frames; make sheets.
python qa_event.py <prefix> "<plan>" <secs> [iv]   (RA must be running with the state loaded)"""
import sys, time, os
import qa_lib as q, qa_walk, ra
from PIL import Image, ImageChops
pre, plan, secs = sys.argv[1], sys.argv[2], float(sys.argv[3]); iv = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
if plan != '-': qa_walk.run(plan, kill=False)
t0 = time.time(); keep = []; last = None; n = 0
while time.time() - t0 < secs:
    time.sleep(iv)
    name = '%s_%03d' % (pre, n); n += 1
    p = q.snap(name)
    im = Image.open(p).convert('L').resize((160, 120))
    if last is not None and sum(ImageChops.difference(im, last).get_flattened_data()) / 19200 < 0.15:
        os.remove(p); continue
    last = im; keep.append(name)
for k in range(0, len(keep), 16):
    q.sheet(keep[k:k + 16], '%s_sheet%d.png' % (pre, k // 16))
print(len(keep), 'frames kept')

