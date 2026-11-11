"""Interactive walking helper. python qa_walk.py "<plan>" <snapname>
plan: 'right:3,right+cross:0.5,up:1' (buttons joined by +, seconds). Kills enemies + keeps HP up while moving.
Prints stage id, room bounds (map x0,y0,x1,y1), player x,y."""
import sys, time, struct
import qa_lib as q, ra

def info():
    st = q.r8(0x800974A0)
    b = struct.unpack('<8i', q.r(0x800730B0, 32))
    p = q.r(0x800733D8, 8)
    px, py = struct.unpack_from('<h', p, 2)[0], struct.unpack_from('<h', p, 6)[0]
    return 'stage=%02x room x%d-%d y%d-%d  player %d,%d' % (st, b[0], b[2], b[1], b[3], px, py)

def run(plan, kill=True):
    for part in plan.split(','):
        d, _, t = part.partition(':'); m = 0
        for k in d.split('+'):
            if k and k != 'none': m |= ra.BTN[k]
        t = float(t or 1); t0 = time.time()
        ra.setpad(m)
        while time.time() - t0 < t:
            if kill:
                q.killall_enemies(); q.w(0x80097BB4, 5000); q.w(0x80097BB8, 5000); q.w(0x80097BC4, 99); q.w(0x80097BC8, 99)
            time.sleep(0.1)
    ra.setpad(0)

if __name__ == '__main__':
    run(sys.argv[1], kill='nokill' not in sys.argv)
    time.sleep(0.3)
    if len(sys.argv) > 2 and sys.argv[2] != 'nokill':
        q.snap(sys.argv[2])
    print(info())

