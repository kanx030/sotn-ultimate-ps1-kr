"""Boot <cue>, go to file select, write Korean over 'Select file to be loaded', snap."""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
import ra, st0text
cue, out = sys.argv[1], sys.argv[2]
__import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA, '--config', ra.CFG, '-L', ra.CORE, cue])
time.sleep(25)
ra.press('start:0.3 wait:4 start:0.3 wait:4')
b = st0text.enc(sys.argv[3] if len(sys.argv) > 3 else '불러올 파일을 고르세요') + b'\0'
a = 0x801B0178 & 0x1FFFFF
ra.cmd('WRITE_CORE_RAM %x %s' % (a, ' '.join('%02x' % x for x in b)))
time.sleep(0.5); print(ra.mem(0x801B0178, len(b)).hex())
ra.press('cross:0.3 wait:3')
ra.snap(out + '_1.png'); ra.press('circle:0.3 wait:2'); ra.press('cross:0.3 wait:3'); ra.snap(out + '_2.png')
