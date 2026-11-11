"""English reference build (only the --test pad hook + font engine, no text changes) for timing comparison."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import build, imgpatch
build.TEST = True
out = sys.argv[1]
p = imgpatch.Patcher(build.SRC_IMG, out)
p.write_file('/SLUS_000.67;1', build.patch_exe(build.read(os.path.join(build.U, 'SLUS_000.67'))))
d = bytearray(build.read(os.path.join(build.U, 'DRA.BIN')))
o = 0x800E6914 - 0x800A0000
d[o:o + 4] = build.jal_word(build.PADHOOK_RAM)
p.write_file('/DRA.BIN;1', bytes(d))
st0 = bytearray(build.read(os.path.join(build.U, 'ST', 'ST0', 'ST0.BIN')))
pass
p.write_file('/ST/ST0/ST0.BIN;1', bytes(st0))
p.close()
open(os.path.splitext(out)[0] + '.cue', 'w').write('FILE "%s" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n' % os.path.basename(out))
print('built', out)
