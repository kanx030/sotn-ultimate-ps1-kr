"""Minimal R3000 assembler for small patches."""
import struct
R = {n: i for i, n in enumerate(['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
     's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra'])}

def _i(op, rs, rt, imm): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (imm & 0xFFFF)
def _r(fn, rs='zero', rt='zero', rd='zero', sa=0): return (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | (sa << 6) | fn

class Asm:
    def __init__(self, base):
        self.base = base; self.words = []; self.labels = {}; self.fix = []
    @property
    def pc(self): return self.base + 4 * len(self.words)
    def label(self, n): self.labels[n] = self.pc
    def w(self, x): self.words.append(x & 0xFFFFFFFF)
    # instructions
    def nop(self): self.w(0)
    def lui(self, rt, imm): self.w(_i(15, 'zero', rt, imm))
    def ori(self, rt, rs, imm): self.w(_i(13, rs, rt, imm))
    def andi(self, rt, rs, imm): self.w(_i(12, rs, rt, imm))
    def addiu(self, rt, rs, imm): self.w(_i(9, rs, rt, imm))
    def sltiu(self, rt, rs, imm): self.w(_i(11, rs, rt, imm))
    def slti(self, rt, rs, imm): self.w(_i(10, rs, rt, imm))
    def lw(self, rt, off, rs): self.w(_i(35, rs, rt, off))
    def sw(self, rt, off, rs): self.w(_i(43, rs, rt, off))
    def lbu(self, rt, off, rs): self.w(_i(36, rs, rt, off))
    def lhu(self, rt, off, rs): self.w(_i(37, rs, rt, off))
    def lh(self, rt, off, rs): self.w(_i(33, rs, rt, off))
    def sb(self, rt, off, rs): self.w(_i(40, rs, rt, off))
    def sh(self, rt, off, rs): self.w(_i(41, rs, rt, off))
    def addu(self, rd, rs, rt): self.w(_r(33, rs, rt, rd))
    def subu(self, rd, rs, rt): self.w(_r(35, rs, rt, rd))
    def or_(self, rd, rs, rt): self.w(_r(37, rs, rt, rd))
    def and_(self, rd, rs, rt): self.w(_r(36, rs, rt, rd))
    def sltu(self, rd, rs, rt): self.w(_r(43, rs, rt, rd))
    def sllv(self, rd, rt, rs): self.w(_r(4, rs, rt, rd))
    def srlv(self, rd, rt, rs): self.w(_r(6, rs, rt, rd))
    def sll(self, rd, rt, sa): self.w(_r(0, 'zero', rt, rd, sa))
    def srl(self, rd, rt, sa): self.w(_r(2, 'zero', rt, rd, sa))
    def jr(self, rs): self.w(_r(8, rs))
    def jalr(self, rs, rd='ra'): self.w(_r(9, rs, 'zero', rd))
    def li(self, rt, v):
        v &= 0xFFFFFFFF
        if v >> 16:
            self.lui(rt, v >> 16)
            if v & 0xFFFF: self.ori(rt, rt, v & 0xFFFF)
        else:
            self.ori(rt, 'zero', v)
    def j(self, tgt): self._jump(2, tgt)
    def jal(self, tgt): self._jump(3, tgt)
    def _jump(self, op, tgt):
        if isinstance(tgt, str): self.fix.append((len(self.words), 'j', tgt)); self.w(op << 26)
        else: self.w((op << 26) | ((tgt >> 2) & 0x3FFFFFF))
    def _br(self, op, rs, rt, tgt):
        self.fix.append((len(self.words), 'b', tgt)); self.w(_i(op, rs, rt, 0))
    def beq(self, rs, rt, t): self._br(4, rs, rt, t)
    def bne(self, rs, rt, t): self._br(5, rs, rt, t)
    def blez(self, rs, t): self._br(6, rs, 'zero', t)
    def bgtz(self, rs, t): self._br(7, rs, 'zero', t)
    def b(self, t): self.beq('zero', 'zero', t)
    def data(self, b):
        b = bytes(b) + b'\0' * (-len(b) % 4)
        for k in range(0, len(b), 4): self.w(struct.unpack('<I', b[k:k + 4])[0])
    def assemble(self):
        for idx, kind, lab in self.fix:
            tgt = self.labels[lab] if isinstance(lab, str) else lab
            if kind == 'j':
                self.words[idx] |= (tgt >> 2) & 0x3FFFFFF
            else:
                pc = self.base + 4 * idx
                off = (tgt - pc - 4) >> 2
                assert -32768 <= off < 32768
                self.words[idx] |= off & 0xFFFF
        return b''.join(struct.pack('<I', x) for x in self.words)

def jal_word(tgt): return struct.pack('<I', (3 << 26) | ((tgt >> 2) & 0x3FFFFFF))
