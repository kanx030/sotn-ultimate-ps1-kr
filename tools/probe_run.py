"""Load state, apply a probe module (probe / probe2), play the prologue dialogue, print results."""
import sys, time, os, importlib
sys.path.insert(0, os.path.dirname(__file__))
import ra
ra.cmd('LOAD_STATE'); time.sleep(5)
sys.argv = [sys.argv[0], '0.2'] if len(sys.argv) < 2 else sys.argv
mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1][0].isdigit() else 'probe')
ra.setpad(ra.BTN['left'] | ra.BTN['up']); time.sleep(24)
ra.setpad(ra.BTN['left']); time.sleep(8); ra.setpad(0); time.sleep(3)
if hasattr(mod, 'dump'):
    mod.dump()
else:
    print('a1/count', ra.mem(0x801FB900, 8).hex(' '))
ra.snap(os.path.join(r'E:\SOTNKR\test\screenshots', 'probe.png'))
