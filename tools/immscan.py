"""Find code address immediates (lui+addiu/ori) whose target inside a cutscene script changed bytes."""
import sys, struct, os
sys.path.insert(0, r'E:\SOTNKR\tools')
import iso, scriptcheck as sc
img = iso.Img(sys.argv[1]); base = sys.argv[2]
for e in img.walk():
    p = e['path'].split(';')[0]
    if e['dir'] or not p.upper().endswith('.BIN'): continue
    of = os.path.join(base, p.lstrip('/'))
    if not os.path.exists(of): continue
    o = open(of, 'rb').read(); n = img.read_file(e['lba'], e['size'])
    if o == n or not sc.scripts(o): continue
    lo_s = min(s for _, s, _ in sc.scripts(o)); hi_s = max(x for _, _, x in sc.scripts(o))
    w = lambda a: struct.unpack_from('<I', o, a)[0]
    for a in range(0, len(o) - 4, 4):
        x = w(a)
        if x >> 26 != 15: continue
        rt = (x >> 16) & 31; hi = x & 0xFFFF
        for b in range(a + 4, min(len(o) - 4, a + 40), 4):
            y = w(b)
            if y >> 26 in (9, 13) and (y >> 21) & 31 == rt:
                lo = y & 0xFFFF
                t = (hi << 16) + (lo - 0x10000 if (y >> 26 == 9 and lo & 0x8000) else lo) - 0x80180000
                if lo_s - 0x400 <= t < hi_s + 0x400 and 0 <= t < len(o) and o[t:t+4] != n[t:t+4]:
                    print(p, 'code %x -> %x orig %s built %s' % (0x80180000 + b, 0x80180000 + t, o[t:t+6].hex(), n[t:t+6].hex()))
                break
