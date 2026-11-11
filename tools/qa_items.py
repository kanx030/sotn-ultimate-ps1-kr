"""Use consumables by writing them into the right-hand slot and pressing square; frame-captures pop-ups.
python qa_items.py id1 id2 ...  (needs RA running with a state loaded)"""
import sys, time
import qa_lib as q, qa_frames as f, ra
for a in sys.argv[1:]:
    iid = int(a)
    q.w(0x80097BB4, 30)            # lower HP so potions show recovery
    q.w(0x80097C14, iid)
    time.sleep(0.6)
    ns = f.capture('f_use_%03d' % iid, 8, 7, pre=lambda: (ra.setpad(ra.BTN['square']), [ra.cmd('FRAMEADVANCE') or time.sleep(0.03) for _ in range(4)], ra.setpad(0)))
    q.sheet(ns, 'sheet_use_%03d.png' % iid)
    time.sleep(1.5)
q.w(0x80097C14, 0x7b)
