"""Binary fix for an already-built image: code immediates (lui/addiu) naming a cutscene command that moved when
the script was re-packed (BO2 post-fight freeze). New target = where the original command bytes now are."""
import sys, struct
sys.path.insert(0, r'E:\SOTNKR\tools')
import iso, imgpatch
src, dst, base = sys.argv[1:4]
FIX = {'/BOSS/BO2/BO2.BIN': [(0x801a6314, 0x80181dc5)],
       '/BOSS/BO6/BO6.BIN': [(0x801a88c4, 0x8019a2e1), (0x801a8904, 0x8019a2fb)],
       '/BIN/BO6RIC2.BIN': [(0x801a88c4, 0x8019a2e1), (0x801a8904, 0x8019a2fb)],
       '/BOSS/RBO6/RBO6.BIN': [(0x801a3210, 0x801819e7)],
       '/ST/DRE/DRE.BIN': [(0x80195ffc, 0x80181b65)],
       '/ST/RCEN/RCEN.BIN': [(0x8019ebb8, 0x801818d5)]}
B = 0x80180000
im = imgpatch.Patcher(src, dst) if hasattr(imgpatch, 'Patcher') else None
for e in im.img.walk():
    p = e['path'].split(';')[0]
    if p not in FIX: continue
    n = bytearray(im.img.read_file(e['lba'], e['size']))
    o = open(base + p, 'rb').read()
    for ins, t in FIX[p]:
        a = ins - B; y = struct.unpack_from('<I', n, a)[0]
        assert y >> 26 == 9 and (y & 0xFFFF) == (t & 0xFFFF), (p, hex(ins), hex(y))
        key = o[t - B:t - B + 8]
        hits = [k for k in range(t - B - 0x200, t - B + 0x200) if n[k:k + 8] == key]
        assert len(hits) == 1, (p, hex(t), hits)
        nt = hits[0] + B
        assert nt >> 16 == t >> 16 and (nt & 0x8000) == (t & 0x8000)
        struct.pack_into('<I', n, a, (y & 0xFFFF0000) | (nt & 0xFFFF))
        print(p, '%x: %x -> %x' % (ins, t, nt))
    im.write_file(e['path'], bytes(n))
im.close()
