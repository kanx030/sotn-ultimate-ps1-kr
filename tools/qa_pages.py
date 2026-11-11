"""Pick 'page complete' frames of a captured cutscene (frame before text-box pixel count drops) and stack box crops.
python qa_pages.py <prefix> <out_prefix> [y0 y1]"""
import sys, glob, os
from PIL import Image
QA = r'E:\SOTNKR\test\qa'
pre, out = sys.argv[1], sys.argv[2]
y0, y1 = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (430, 680)
fs = sorted(glob.glob(os.path.join(QA, pre + '_[0-9][0-9][0-9].png')))
def textpx(f):
    im = Image.open(f).convert('L').crop((230, y0 + 40, 956, y1 - 20))
    return sum(1 for v in im.get_flattened_data() if v > 200)
c = [textpx(f) for f in fs]
pick = []
for i in range(len(fs)):
    nxt = c[i + 1] if i + 1 < len(fs) else -1
    if c[i] > 30 and nxt < c[i] * 0.85:
        pick.append(fs[i])
crops = [Image.open(f).convert('RGB').crop((0, y0, 956, y1)) for f in pick]
per = 6
for k in range(0, len(crops), per):
    part = crops[k:k + per]
    s = Image.new('RGB', (956, (y1 - y0 + 4) * len(part)), (255, 0, 255))
    for i, im in enumerate(part):
        s.paste(im, (0, i * (y1 - y0 + 4)))
    s.save(os.path.join(QA, '%s_%d.png' % (out, k // per)))
print(len(pick), [os.path.basename(p) for p in pick])
