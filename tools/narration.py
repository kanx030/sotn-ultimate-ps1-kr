"""Japanese narration for the opening crawl (JP dub), taken from the Japanese disc at build time.

The JP release plays XA id 0x33D at the crawl (music + Japanese narration); Ultimate/US plays 0x340 (music
only) and the narrated track is not on the Ultimate disc. The build copies the narrated stream's interleaved
region (8 channels, the narration is channel 6, file 0x1E) raw from the user's JP disc to the end of our image
and makes DRA's XA lookup return a new entry for index 0x40 (id 0x340) when the dub is JP:

  DRA 0x80131C7C..CAC (13 words, originally: index 0x3F + PSP dub -> alternate entry 0x800E20E4) becomes
    lui v0,0x8009; lbu v0,0x7BAF(v0); addiu v1,s1,-0x3F; andi v0,v0,0x28; sll at,v1,5
    bne v0,at,CB0        # passes only for (index 0x3F, flag 0) or (index 0x40, flag 0x20); other v1 never fit
    lui v0,0x800E
    bne v1,zero,is40
    addiu v0,v0,0x20E4
    j 0x80131E00; nop    # 0x3F/PSP: unchanged behaviour
  is40: lui s4,hi(ENT); addiu s4,s4,lo(ENT)   # then falls into CB0, which returns s4 for index 0x40
  ENT (16 bytes, font RAM just below the ext area) = JP entry {offset = appended LBA - XA_STR1 LBA, 0x1893,
  file 0x1E, channel 6, volume 0x7A, 2}. The player computes LBA = XA base + offset + channel.

The audio is copyrighted game data: it only goes into the built image (and so into the release xdelta);
never into git. Disc path: env SOTN_JP_DISC, else the Rev 2 track 1 in the project root. Without the disc the
saved region work/narrsrc/jp_crawl_region.bin (env SOTN_JP_REGION) is used: the raw region cut from a built
image (e.g. the v1.0 release = original + xdelta); it holds the same stream (checked by the same md5).
python narration.py [wav]   -> extract + decode to work/narr/*.wav for listening (checks only)"""
import os, sys, struct, hashlib
from addrmap import dra as _R      # DRA address of the old base (v1.2) -> current base, signature-checked
sys.path.insert(0, os.path.dirname(__file__))
from asm import Asm

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
JP_DISC = os.environ.get('SOTN_JP_DISC') or os.path.join(
    ROOT, 'Akumajou Dracula X - Gekka no Yasoukyoku (Japan) (Rev 2) (Track 1).bin')
REGION = os.environ.get('SOTN_JP_REGION') or os.path.join(ROOT, 'work', 'narrsrc', 'jp_crawl_region.bin')
SEC = 2352
JP_XA_LBA = 47643          # SD/XA_STR1 on the JP disc (Rev 0 and Rev 2)
def _xa_lba():
    import iso, base
    return [e for e in iso.Img(base.SRC_IMG).walk() if e['path'].upper().startswith('/SD/XA_STR1')][0]['lba']
U_XA_LBA = _xa_lba()       # SD/XA_STR1 on Ultimate (= DRA XA base 0x80138F20): v1.2 51894, v1.4 52588
JP_OFF, JP_LEN, FILE, CHAN, VOL, KIND = 0x64D0, 0x1893, 0x1E, 6, 0x7A, 2   # JP DRA 0x800BD390 entry 0x33D
GROUPS = 1966              # channel-6 sectors with file 0x1E (~104.9 s; len 0x1893 = frames)
TAIL = 75                  # extra interleave groups copied after the stream (drive read-ahead)
NSEC = (GROUPS + TAIL) * 8
STREAM_MD5 = '92396d6e5eea57c2887ca4b912cddfb3'   # md5 of the 1966 stream sectors [16:2352] (Rev 2 dump; hash only)
ENT_RAM = None             # set by build (font area)
LOOK = _R(0x80131C7C)
ORIG_LOOK = bytes.fromhex('3f0002340b002216000000000980023caf7b4290000000002800423005004014'
                          '000000000e80023ce420422480c7040800000000')

def disc_ok(path=JP_DISC):
    return os.path.exists(path) or os.path.exists(REGION)

def read_region(path=JP_DISC):
    """Raw interleaved region (NSEC sectors) from the JP disc; checks the stream's subheaders."""
    src, at = (path, (JP_XA_LBA + JP_OFF) * SEC) if os.path.exists(path) else (REGION, 0)
    with open(src, 'rb') as f:
        f.seek(at)
        reg = f.read(NSEC * SEC)
    assert len(reg) == NSEC * SEC, 'JP disc too short'
    h = hashlib.md5()
    for g in range(GROUPS):
        s = reg[(g * 8 + CHAN) * SEC:(g * 8 + CHAN + 1) * SEC]
        assert s[16:20] == bytes([FILE, CHAN, 0x64, 1]) and s[16:20] == s[20:24], \
            'JP disc: unexpected subheader at group %d (%s) - not the expected Japanese disc?' % (g, s[16:20].hex())
        h.update(s[16:SEC])
    s = reg[(GROUPS * 8 + CHAN) * SEC:][:24]
    assert s[16] != FILE, 'stream longer than expected'
    if STREAM_MD5 and h.hexdigest() != STREAM_MD5:
        raise AssertionError('JP disc: narration stream differs from the verified dump (md5 %s)' % h.hexdigest())
    return reg

def channel(reg, ch=CHAN, n=GROUPS):
    return [reg[(g * 8 + ch) * SEC:(g * 8 + ch + 1) * SEC] for g in range(n)]

def bcd(n): return ((n // 10) << 4) | (n % 10)

def append(img_f, reg):
    """Append the region at the image end (img_f opened r+b). Returns the first LBA."""
    img_f.seek(0, 2); end = img_f.tell()
    assert end % SEC == 0
    lba0 = end // SEC
    out = bytearray(reg)
    for i in range(NSEC):                     # sector headers carry the new position (form 2: EDC excludes it)
        m, r = divmod(lba0 + i + 150, 75 * 60); s, fr = divmod(r, 75)
        out[i * SEC + 12:i * SEC + 15] = bytes([bcd(m), bcd(s), bcd(fr)])
    img_f.write(out)
    return lba0

def entry(lba0):
    return struct.pack('<IIBBBBI', lba0 - U_XA_LBA, JP_LEN, FILE, CHAN, VOL, 0, KIND)

def patch_dra(dra, ent_ram):
    dra = bytearray(dra)
    o = LOOK - 0x800A0000
    w = lambda k: struct.unpack_from('<I', dra, o + 4 * k)[0]
    # the original 13 words with the alternate entry (lui/addiu) and the j target masked (they move per version)
    cur = bytearray(dra[o:o + 52]); ref = bytearray(ORIG_LOOK)
    for k in (9, 10, 11):
        cur[4 * k:4 * k + 2] = ref[4 * k:4 * k + 2] = b'\0\0'
    cur[44:47] = ref[44:47] = b'\0\0\0'
    assert cur == ref, dra[o:o + 52].hex()
    alt = ((w(9) & 0xFFFF) << 16) + (((w(10) & 0xFFFF) ^ 0x8000) - 0x8000)
    jt = (LOOK & 0xF0000000) | ((w(11) & 0x3FFFFFF) << 2)
    a = Asm(LOOK)
    a.lui('v0', 0x8009); a.lbu('v0', 0x7BAF, 'v0'); a.addiu('v1', 's1', -0x3F); a.andi('v0', 'v0', 0x28)
    a.sll('at', 'v1', 5)
    a.bne('v0', 'at', LOOK + 0x34); a.lui('v0', (alt + 0x8000) >> 16)
    a.bne('v1', 'zero', 'is40'); a.addiu('v0', 'v0', alt & 0xFFFF)
    a.j(jt); a.nop()
    a.label('is40')
    a.lui('s4', (ent_ram + 0x8000) >> 16); a.addiu('s4', 's4', ent_ram & 0xFFFF)
    c = a.assemble(); assert len(c) == 52
    dra[o:o + 52] = c
    return bytes(dra)

ENABLED = False
LBA0 = None

def add_to_image(img_f, test):
    """Build step: append the stream (release builds require the JP disc; --test builds only warn)."""
    global ENABLED, LBA0
    if not disc_ok():
        msg = 'JP disc not found (%s): opening-crawl narration needs it (set SOTN_JP_DISC)' % JP_DISC
        if not test:
            raise SystemExit('narration: ' + msg)
        print('narration: WARNING ' + msg + ' - skipped'); ENABLED = False; return
    LBA0 = append(img_f, read_region()); ENABLED = True
    print('narration: JP crawl stream appended at LBA %d (%d sectors)' % (LBA0, NSEC))

# ---- XA ADPCM decode (checks / listening only) ----
K0 = [0, 60, 115, 98, 122]; K1 = [0, 0, -52, -55, -60]

def decode(sectors):
    """4-bit stereo XA sectors -> interleaved int16 list (L,R,...)."""
    import numpy as np
    out = []; old = [[0, 0], [0, 0]]
    for s in sectors:
        assert s[19] & 0x3F == 1, 'expected 4-bit stereo 37.8 kHz'
        d = s[24:24 + 18 * 128]
        for g in range(18):
            grp = d[g * 128:(g + 1) * 128]
            L = []; R = []
            for u in range(8):
                p = grp[4 + u]; sh = p & 0xF; fl = min(p >> 4, 4)
                ch = u & 1; o1, o2 = old[ch]; dst = L if ch == 0 else R
                blk = []
                for i in range(28):
                    nb = (grp[16 + i * 4 + (u >> 1)] >> ((u & 1) * 4)) & 0xF
                    v = (nb - 16 if nb & 8 else nb) << 12
                    v = (v >> sh) if sh <= 12 else v >> 12
                    v += (o1 * K0[fl] + o2 * K1[fl] + 32) >> 6
                    v = max(-32768, min(32767, v)); o2, o1 = o1, v; blk.append(v)
                old[ch] = [o1, o2]; dst.extend(blk)
            for l, r in zip(L, R): out += [l, r]
    return np.array(out, dtype=np.int16)

def write_wav(path, pcm, rate=37800):
    import wave
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())

def main():
    import numpy as np
    sys.path.insert(0, os.path.dirname(__file__)); import iso
    od = os.path.join(ROOT, 'work', 'narr'); os.makedirs(od, exist_ok=True)
    reg = read_region()
    jp = decode(channel(reg))
    h = hashlib.md5(b''.join(s[16:] for s in channel(reg))).hexdigest()
    print('JP narration stream: %d sectors, %.1f s, md5 %s' % (GROUPS, len(jp) / 2 / 37800, h))
    write_wav(os.path.join(od, 'jp_narration_33D.wav'), jp)
    u = iso.Img(__import__('base').SRC_IMG)
    us = [u.raw(U_XA_LBA + 0x2BC80 + 4 + 8 * g) for g in range(GROUPS)]
    us = [s for s in us if s[16:18] == bytes([6, 4])]
    um = decode(us)
    write_wav(os.path.join(od, 'ultimate_music_340.wav'), um)
    n = min(len(jp), len(um))
    a = jp[:n].astype(float); b = um[:n].astype(float)
    print('JP rms %.0f, Ultimate rms %.0f, rms(JP-Ultimate) %.0f, corr %.3f' % (
        a.std(), b.std(), (a - b).std(), np.corrcoef(a, b)[0, 1]))
    for t in range(0, int(n / 2 / 37800), 10):   # per 10 s: JP vs music level
        sl = slice(t * 75600, (t + 10) * 75600)
        print('  %3d s: JP %6.0f  music %6.0f  diff %6.0f' % (t, a[sl].std(), b[sl].std(), (a[sl] - b[sl]).std()))

if __name__ == '__main__':
    main()
