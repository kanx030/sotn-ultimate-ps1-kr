"""Stack crops of QA screenshots. python qa_crop.py <out> <x0,y0,x1,y1> <scale> name1 name2 ..."""
import sys, os
from PIL import Image
QA = r'E:\SOTNKR\test\qa'
out, box, sc = sys.argv[1], tuple(int(v) for v in sys.argv[2].split(',')), float(sys.argv[3])
ims = [Image.open(os.path.join(QA, n if n.endswith('.png') else n + '.png')).convert('RGB').crop(box) for n in sys.argv[4:]]
w, h = ims[0].size; w2, h2 = int(w * sc), int(h * sc)
s = Image.new('RGB', (w2, (h2 + 4) * len(ims)), (255, 0, 255))
for i, im in enumerate(ims):
    s.paste(im.resize((w2, h2), Image.NEAREST), (0, i * (h2 + 4)))
s.save(os.path.join(QA, out))
