"""Print RAM patch args (addr=hex) for run_state.py: KST0 code + diff of patched vs original ST0."""
import os, build
u = open(os.path.join(build.U, 'ST', 'ST0', 'ST0.BIN'), 'rb').read()
import st0text
p = st0text.patch(build.patch_st0(u))
args = ['%x=%s' % (build.KST0_RAM, build.kst0_code().hex()), '%x=%s' % (build.KTAB_RAM, build.ktab().hex())]
i = 0
while i < len(u):
    if u[i] != p[i]:
        j = i
        while j < len(u) and (u[j] != p[j] or j - i < 4 and j % 4): j += 1
        a = i & ~3; b = (j + 3) & ~3
        args.append('%x=%s' % (0x80180000 + a, p[a:b].hex())); i = b
    else: i += 1
print(' '.join(args))
