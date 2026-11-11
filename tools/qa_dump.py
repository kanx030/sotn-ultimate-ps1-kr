"""Load a state file and dump main RAM (2MB) to test/qa/ram_<name>.bin. python qa_dump.py <state.bak> <name> [snap]"""
import sys, time
import qa_lib as q, ra
bak, name = sys.argv[1], sys.argv[2]
q.boot(bak, wait=4)
ra.cmd('PAUSE_TOGGLE'); time.sleep(0.5)
d = q.r(0x80000000, 0x200000)
open(r'E:\SOTNKR\test\qa\ram_%s.bin' % name, 'wb').write(d)
q.snap('dump_' + name)
ra.cmd('PAUSE_TOGGLE')
print(len(d))
