"""Tiny R3000 disassembler. python mips.py file fileoff vaddr count"""
import struct, sys
R = ['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
     's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra']

def dis(w, pc):
    op = w >> 26; rs = (w >> 21) & 31; rt = (w >> 16) & 31; rd = (w >> 11) & 31
    sa = (w >> 6) & 31; fn = w & 63; imm = w & 0xFFFF; simm = imm - 0x10000 if imm & 0x8000 else imm
    tgt = (pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
    br = (pc + 4 + (simm << 2)) & 0xFFFFFFFF
    if w == 0: return 'nop'
    if op == 0:
        n = {0:'sll',2:'srl',3:'sra'}.get(fn)
        if n: return '%s %s,%s,%d' % (n, R[rd], R[rt], sa)
        n = {4:'sllv',6:'srlv',7:'srav'}.get(fn)
        if n: return '%s %s,%s,%s' % (n, R[rd], R[rt], R[rs])
        if fn == 8: return 'jr %s' % R[rs]
        if fn == 9: return 'jalr %s,%s' % (R[rd], R[rs])
        if fn == 12: return 'syscall'
        if fn == 13: return 'break'
        n = {16:'mfhi',18:'mflo'}.get(fn)
        if n: return '%s %s' % (n, R[rd])
        n = {17:'mthi',19:'mtlo'}.get(fn)
        if n: return '%s %s' % (n, R[rs])
        n = {24:'mult',25:'multu',26:'div',27:'divu'}.get(fn)
        if n: return '%s %s,%s' % (n, R[rs], R[rt])
        n = {32:'add',33:'addu',34:'sub',35:'subu',36:'and',37:'or',38:'xor',39:'nor',42:'slt',43:'sltu'}.get(fn)
        if n: return '%s %s,%s,%s' % (n, R[rd], R[rs], R[rt])
        return '.word %08x' % w
    if op == 1:
        n = {0:'bltz',1:'bgez',16:'bltzal',17:'bgezal'}.get(rt, 'regimm?')
        return '%s %s,%08x' % (n, R[rs], br)
    if op == 2: return 'j %08x' % tgt
    if op == 3: return 'jal %08x' % tgt
    if op in (4, 5): return '%s %s,%s,%08x' % ('beq' if op == 4 else 'bne', R[rs], R[rt], br)
    if op in (6, 7): return '%s %s,%08x' % ('blez' if op == 6 else 'bgtz', R[rs], br)
    n = {8:'addi',9:'addiu',10:'slti',11:'sltiu'}.get(op)
    if n: return '%s %s,%s,%d' % (n, R[rt], R[rs], simm)
    n = {12:'andi',13:'ori',14:'xori'}.get(op)
    if n: return '%s %s,%s,0x%x' % (n, R[rt], R[rs], imm)
    if op == 15: return 'lui %s,0x%x' % (R[rt], imm)
    if op == 16 or op == 18:
        return 'cop%d %08x' % (op - 16, w)
    n = {32:'lb',33:'lh',34:'lwl',35:'lw',36:'lbu',37:'lhu',38:'lwr',40:'sb',41:'sh',42:'swl',43:'sw',50:'lwc2',58:'swc2'}.get(op)
    if n: return '%s %s,%d(%s)' % (n, R[rt], simm, R[rs])
    return '.word %08x' % w

def listing(data, off, vaddr, count):
    out = []
    for i in range(count):
        w = struct.unpack('<I', data[off + 4 * i:off + 4 * i + 4])[0]
        pc = vaddr + 4 * i
        out.append('%08x %06x: %08x  %s' % (pc, off + 4 * i, w, dis(w, pc)))
    return out

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[2], 16); va = int(sys.argv[3], 16); n = int(sys.argv[4])
    print('\n'.join(listing(d, off, va, n)))
