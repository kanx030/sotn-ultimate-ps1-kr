"""Load state slot 0 (prologue start), inject Korean test line into RAM, walk to Dracula, snapshot."""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra, texttest
from PIL import Image

ra.cmd('LOAD_STATE'); time.sleep(6)
us = b"Dracula. Die now, and\x01\x03\x04leave this world!\x01\x03\x04You'll never belong\x01\x03\x04here!"
addr = 0x80180000 + ra.mem(0x80180000, 0x80000).find(us)
print('ram matches', ra.mem(addr, len(us)) == us)
kr = texttest.KR
pad = len(us) - len(kr); kr += b'\x81\x40' * (pad // 2) + b' ' * (pad % 2)
for k in range(0, len(kr), 32):
    ch = kr[k:k + 32]
    ra.cmd('WRITE_CORE_RAM %x %s' % ((addr & 0x1FFFFF) + k, ' '.join('%02x' % b for b in ch)))
print('written', ra.mem(addr, len(us)) == kr)
ra.setpad(ra.BTN['left'] | ra.BTN['up'])
shots = []
for i in range(8):
    time.sleep(3); shots.append(ra.snap('test/screenshots/w_%02d.png' % i))
ra.setpad(0)
for i in range(4):
    time.sleep(2); shots.append(ra.snap('test/screenshots/w_%02d.png' % (8 + i)))
s = Image.new('RGB', (320 * 4, 240 * 3))
for i, f in enumerate(shots):
    s.paste(Image.open(f).convert('RGB').resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
s.save('test/screenshots/w_sheet.png')

