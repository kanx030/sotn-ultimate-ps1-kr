"""Write file contents back into a MODE2/2352 image (in place, same or smaller sector count),
recomputing EDC/ECC. Also supports relocating a grown file to the image end."""
import struct, shutil, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import iso
import numpy as np
from chd2bin import _ecc_block, _PIDX, _QIDX, SYNC

def _edc_table():
    t = []
    for i in range(256):
        e = i
        for _ in range(8):
            e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
        t.append(e)
    return t
EDC = _edc_table()

def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC[(e ^ b) & 0xFF]
    return e

def build_form1(sec, payload, lba=None):
    """sec: original raw sector (bytearray) - keeps header/subheader; payload 2048 bytes."""
    s = bytearray(sec)
    s[24:24 + 2048] = payload
    s[2072:2076] = struct.pack('<I', edc(bytes(s[16:2072])))
    arr = np.frombuffer(bytes(s), np.uint8).reshape(1, 2352).copy()
    src = arr[:, 12:].copy(); src[:, 0:4] = 0
    p = _ecc_block(src[:, :2064], _PIDX); src[:, 2064:2236] = p
    q = _ecc_block(src[:, :2236], _QIDX)
    arr[:, 0x81C:0x81C + 172] = p; arr[:, 0x8C8:0x8C8 + 104] = q
    return arr.tobytes()

def bcd(n): return ((n // 10) << 4) | (n % 10)

def make_sector(lba, payload, submode=0x08, eof=False):
    s = bytearray(2352)
    s[0:12] = SYNC
    m, r = divmod(lba + 150, 75 * 60); sec, f = divmod(r, 75)
    s[12:16] = bytes([bcd(m), bcd(sec), bcd(f), 2])
    sm = submode | (0x81 if eof else 0)
    s[16:20] = bytes([0, 0, sm, 0]); s[20:24] = s[16:20]
    return build_form1(s, payload)

class Patcher:
    def __init__(self, src, dst):
        if src != dst:
            shutil.copyfile(src, dst)
        self.img = iso.Img(dst, 'r+b')
        self.entries = {e['path'].upper(): e for e in self.img.walk()}

    def write_file(self, path, data):
        e = self.entries[path.upper()]
        nsec_old = (e['size'] + 2047) // 2048
        nsec_new = (len(data) + 2047) // 2048
        if nsec_new > nsec_old:
            raise ValueError('%s grows %d -> %d sectors (relocation not implemented yet)' % (path, nsec_old, nsec_new))
        f = self.img.f
        for i in range(nsec_new):
            lba = e['lba'] + i
            f.seek(lba * 2352); raw = f.read(2352)
            chunk = data[i * 2048:(i + 1) * 2048].ljust(2048, b'\0')
            f.seek(lba * 2352); f.write(build_form1(raw, chunk))
        if len(data) != e['size']:
            self._set_size(e, len(data))

    def _set_size(self, e, size):
        lba, off = e['rec']
        f = self.img.f
        f.seek(lba * 2352); raw = bytearray(f.read(2352))
        d = bytearray(raw[24:24 + 2048])
        d[off + 10:off + 14] = struct.pack('<I', size); d[off + 14:off + 18] = struct.pack('>I', size)
        f.seek(lba * 2352); f.write(build_form1(raw, bytes(d)))
        e['size'] = size

    def close(self):
        self.img.f.close()
