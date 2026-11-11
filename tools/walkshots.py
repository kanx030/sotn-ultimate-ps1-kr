import sys, time, os, threading
sys.path.insert(0, r'E:\SOTNKR\tools')
import ra
from PIL import Image
pre, seq = sys.argv[1], sys.argv[2]
SI = float(os.environ.get('SI', '0.5')); N = int(os.environ.get('N', '12')); D = float(os.environ.get('D', '0'))
def drive():
    for tok in seq.split():
        name, _, hold = tok.partition(':'); hold = float(hold or 1)
        m = 0
        if name != 'none':
            for n in name.split('+'): m |= ra.BTN[n]
        ra.setpad(m); time.sleep(hold)
    ra.setpad(0)
th = threading.Thread(target=drive); th.start()
time.sleep(D)
shots = []
for i in range(N):
    shots.append(ra.snap('%s_%02d.png' % (pre, i))); time.sleep(SI)
th.join()
cols = 4; rows = (len(shots) + cols - 1) // cols
s = Image.new('RGB', (320 * cols, 240 * rows))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % cols) * 320, (i // cols) * 240))
s.save(pre + '_sheet.png'); print(len(shots), ra.mem(0x800974A0, 4).hex())
