"""Phase-1 test: replace the first prologue line (PS1 and PSP scripts) with Korean bytes from the Korean build."""
KR = bytes.fromhex('89df89cd8bde89978149' '0328' '0205' '01' '8ac988d789588944889f8a6f8a7d88bb889f8aa9895b89608142')

def _put(st0, us):
    i = st0.find(us); assert i > 0, us
    kr = KR
    assert len(kr) <= len(us)
    pad = len(us) - len(kr)
    kr += b'\x81\x40' * (pad // 2) + b' ' * (pad % 2)
    st0[i:i + len(us)] = kr

def patch_st0(st0):
    st0 = bytearray(st0)
    _put(st0, b"Die monster.\x01\x03\x1c\x02\x02You don't belong\x01\x03\x08in this world!")
    _put(st0, b"Dracula. Die now, and\x01\x03\x04leave this world!\x01\x03\x04You'll never belong\x01\x03\x04here!")
    return bytes(st0)

def unify_dub(st0):
    """Point the PSP-script branches at the PS1 script so every dub option uses one script/engine."""
    import struct
    for off, psp in ((0x27c88, 0x801a79e8), (0x27f30, 0x801a7c8c)):
        assert struct.unpack_from('<I', st0, off)[0] == psp
        assert struct.unpack_from('<I', st0, off - 4)[0] == 0x801829d8
        struct.pack_into('<I', st0, off, 0x801829d8)
