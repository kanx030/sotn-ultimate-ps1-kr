"""Write the current build's font region (+ext code/glyphs) and a patched overlay into emulator RAM,
so an old save state runs the new code. Used by run_state.py via RAMSYNC=<overlay path like ST/NO3/NO3.BIN>."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import ra, build
build.TEST = True          # keep the --test pad hook in the ext area

def wr(addr, data, chunk=128):
    for k in range(0, len(data), chunk):
        ch = data[k:k + chunk]
        ra.cmd('WRITE_CORE_RAM %x %s' % ((addr & 0x1FFFFF) + k, ' '.join('%02x' % b for b in ch)))

def font_region():
    exe = build.patch_exe(build.read(os.path.join(build.U, 'SLUS_000.67')))
    o = build.exe_off(build.FONT_SRC)
    return exe[o:o + build.COPY_LEN]

def overlay(path):
    fid = build.CUTSCENE_FILES.index(path)
    d = build.patch_cutscene(build.read(os.path.join(build.U, *path.split('/'))), fid, path)
    d, _ = build.patch_names(d, fid)
    if path == 'ST/ST0/ST0.BIN':
        import st0text; d = st0text.patch(d)
    else:
        import transapply; d, _ = transapply.apply(path, d)
    import banner
    return banner.patch(path, d)

def sync(path):
    f = font_region()
    # keep glyph 0 (InitHeap header lives there) untouched
    wr(build.FONT_RAM + 32, f[32:])   # 4-byte aligned writes only (glyph 0 holds the InitHeap header)
    import time
    e = build.EXT_RAM - build.FONT_RAM
    k0 = build.KBUF_RAM - build.EXT_RAM; k1 = k0 + 0xA0           # runtime scratch buffer, skip
    want = f[e:e + build.EXT_SIZE]
    for attempt in range(4):
        time.sleep(0.5)
        got = ra.mem(build.EXT_RAM, build.EXT_SIZE)
        if got[:k0] == want[:k0] and got[k1:] == want[k1:]:
            break
        wr(build.EXT_RAM, want[:k0]); wr(build.EXT_RAM + k1, want[k1:])
    else:
        raise AssertionError('RAM sync of the ext block failed')
    jobs = [(0x800A0000, build.read(os.path.join(build.U, 'DRA.BIN')), build.patch_dra(build.read(os.path.join(build.U, 'DRA.BIN'))))]
    if path:
        jobs.append((0x80180000, build.read(os.path.join(build.U, *path.split('/'))), overlay(path)))
    for base, orig, new in jobs:
        i = 0
        while i < len(orig):
            if orig[i] != new[i]:
                j = i
                while j < len(orig) and (orig[j] != new[j] or any(orig[j + 1:j + 4][k] != new[j + 1:j + 4][k] for k in range(len(orig[j + 1:j + 4])))):
                    j += 1
                a0 = i & ~3; a1 = (j + 4) & ~3
                wr(base + a0, new[a0:a1]); i = a1
            else:
                i += 1
