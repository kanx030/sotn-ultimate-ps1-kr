"""JP-dub voice lengths (Ultimate): table 'UDPJ' in SEL.BIN (copied to 0x8013645C, used by DRA 0x80131CC4 when
flag&0x28 == 0x20). bit (id-0x358) in the bitmap at +124 -> entry word at +184 + 4 * (set bits below it):
low 15 bits sector offset, bits 15..25 length (same unit as the US XA table: frames), bits 26.. channel."""
import struct, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_T = None
def _table():
    global _T
    if _T is None:
        d = open(__import__('base').upath('ST/SEL/SEL.BIN'), 'rb').read()
        _T = d[d.find(b'UDPJ'):]
    return _T

def vid(v):                      # sheet voice '3dd3' -> sound id 0x3d3
    return ((int(v[:2], 16) >> 4) << 8) | int(v[2:], 16)

def length(v):
    t = _table(); s1 = (vid(v) if isinstance(v, str) else v) - 0x300; a1 = s1 - 88
    if not 0 <= a1 < 475 or not (t[124 + (a1 >> 3)] >> (a1 & 7)) & 1: return None
    n = sum((t[124 + (b >> 3)] >> (b & 7)) & 1 for b in range(a1))
    w = struct.unpack_from('<I', t, 184 + 4 * n)[0]
    return (w >> 15) & 0x7FF

if __name__ == '__main__':
    for v in sys.argv[1:]: print(v, length(v))
