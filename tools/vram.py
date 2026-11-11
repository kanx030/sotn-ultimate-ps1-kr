"""VRAM from a RetroArch swanstation state. python vram.py <state> <out.png> [x_hw y w_hw h]  (4bpp grey view)"""
import sys, numpy as np
from PIL import Image
import rzip
BASE = 0x281CD3
def vram(state):
    s = rzip.load(state)
    return np.frombuffer(s[BASE:BASE + 1024 * 512 * 2], np.uint8).reshape(512, 2048)
def view4(v, x, y, w, h):
    a = v[y:y + h, x * 2:(x + w) * 2]
    o = np.zeros((h, w * 4), np.uint8); o[:, 0::2] = a & 15; o[:, 1::2] = a >> 4
    return o
if __name__ == '__main__':
    v = vram(sys.argv[1])
    x, y, w, h = map(int, sys.argv[3:7]) if len(sys.argv) > 3 else (0, 0, 1024, 512)
    if len(sys.argv) > 3:
        Image.fromarray(view4(v, x, y, w, h) * 17).save(sys.argv[2])
    else:
        Image.fromarray(view4(v, 0, 0, 1024, 512) * 17).save(sys.argv[2])
