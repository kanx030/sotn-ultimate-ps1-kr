"""Pause and frame-step, snapping every N frames. Use after setting up a trigger.
import qa_frames; qa_frames.capture('prefix', count, step)"""
import time
import qa_lib as q, ra

def capture(prefix, count=12, step=6, pre=None):
    ra.cmd('PAUSE_TOGGLE'); time.sleep(0.3)
    if pre: pre()
    names = []
    for i in range(count):
        for _ in range(step):
            ra.cmd('FRAMEADVANCE'); time.sleep(0.03)
        time.sleep(0.15)
        n = '%s_%02d' % (prefix, i); q.snap(n); names.append(n)
    ra.cmd('PAUSE_TOGGLE')
    return names
