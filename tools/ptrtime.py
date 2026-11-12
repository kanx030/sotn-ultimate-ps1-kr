"""Load state, walk to Dracula, log when the ST0 script pointer reaches each voice opcode (0b 09 id id).
JP=1 -> sets the JP-dub flag. Prints 'voiceid time'. python ptrtime.py <cue>"""
import sys,time,os,struct,re; sys.path.insert(0,os.path.dirname(__file__)); import ra
cue=sys.argv[1]; JP=os.environ.get('JP')
__import__('ra').kill_own(); time.sleep(1)
ra.subprocess.Popen([ra.RA,'--config',ra.CFG,'-L',ra.CORE,cue])
time.sleep(15); ra.cmd('LOAD_STATE'); time.sleep(12)
if JP: ra.cmd('WRITE_CORE_RAM %x 20'%0x97BAF)
lo,hi=(0x27c00,0x28000) if JP else (0x29d8,0x2c50)
seg=b''.join(ra.mem(0x80180000+o,1024) for o in range(lo,hi,1024))
marks=[(lo+m.start(),m.group()[2:].hex()) for m in re.finditer(rb'\x0b\x09\x35.',seg)]
ra.setpad(ra.BTN['left']|ra.BTN['up']); time.sleep(16); ra.setpad(ra.BTN['left']); time.sleep(0.2); ra.setpad(0)
t0=time.time(); last=None; log=[]
while time.time()-t0<70:
    p=struct.unpack('<I',ra.mem(0x801C2AF8,4))[0]
    if p!=last: log.append((time.time()-t0,p)); last=p
    time.sleep(0.03)
for off,vid in marks:
    t=[a for a,b in log if b>0x80180000+off]; print(vid, round(t[0],2) if t else None)
