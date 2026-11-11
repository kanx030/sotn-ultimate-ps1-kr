"""ISO9660 helper for raw MODE2/2352 PS1 images."""
import struct, sys, os

SEC = 2352

class Img:
    def __init__(self, path, mode='rb'):
        self.path = path
        self.f = open(path, mode)
        self.f.seek(0, 2)
        self.nsec = self.f.tell() // SEC

    def raw(self, lba, n=1):
        self.f.seek(lba * SEC)
        return self.f.read(SEC * n)

    def data(self, lba, n=1):
        r = self.raw(lba, n)
        return b''.join(r[i * SEC + 24:i * SEC + 24 + 2048] for i in range(n))

    def submode(self, lba):
        return self.raw(lba)[18]

    def read_file(self, lba, size):
        n = (size + 2047) // 2048
        return self.data(lba, n)[:size]

    def walk(self):
        pvd = self.data(16)
        assert pvd[1:6] == b'CD001'
        root = pvd[156:156 + 34]
        out = []
        def rec(lba, size, path):
            buf = self.data(lba, (size + 2047) // 2048)
            p = 0
            while p < len(buf):
                ln = buf[p]
                if ln == 0:
                    p = (p // 2048 + 1) * 2048
                    continue
                r = buf[p:p + ln]
                elba = struct.unpack('<I', r[2:6])[0]
                esz = struct.unpack('<I', r[10:14])[0]
                flags = r[25]
                nl = r[32]
                name = r[33:33 + nl]
                recpos = (lba + p // 2048, p % 2048)
                if name not in (b'\0', b'\1'):
                    nm = name.decode('ascii', 'replace')
                    full = path + '/' + nm
                    # XA attrs
                    su = r[33 + nl + ((nl + 1) & 1):]
                    xa = struct.unpack('>H', su[4:6])[0] if len(su) >= 8 and su[6:8] == b'XA' else 0
                    out.append(dict(path=full, lba=elba, size=esz, dir=bool(flags & 2), rec=recpos, xa=xa))
                    if flags & 2:
                        rec(elba, esz, full)
                p += ln
        rec(struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0], '')
        return out

if __name__ == '__main__':
    im = Img(sys.argv[1])
    print('sectors', im.nsec)
    for e in sorted(im.walk(), key=lambda e: e['lba']):
        print('%-40s %8d %10d %s %04x' % (e['path'], e['lba'], e['size'], 'D' if e['dir'] else ' ', e['xa']))
