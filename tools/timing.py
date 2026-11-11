"""Keep the English typing time: the cutscene engine spends <speed> frames per drawn character (opcode 02 xx sets the
speed). Korean is shorter, so pages would end before the voice. Pad each run with a wait (opcode 03 xx, frames)
worth the missing characters, then no-op 0x0D for any odd byte left."""
PAD = 0x0D
_ERR = 0.0

def speed_at(data, off, script_start):
    """Last '02 xx' speed set before off (scan back to the script start). Default 2."""
    i = off - 2
    while i >= script_start:
        if data[i] == 0x02 and data[i + 1] < 0x10 and (i == 0 or data[i - 1] < 0x20 or data[i - 1] >= 0x80):
            return data[i + 1]
        i -= 1
    return 2

def chars(b):
    """number of draw events in an encoded run (2-byte codes count once)."""
    n = 0; i = 0
    while i < len(b):
        if b[i] >= 0x80: i += 2
        else: i += 1
        n += 1
    return n

def pad(b, cap, en_chars, speed):
    """b + trailing spaces (each costs one character time, draws nothing) up to the English character count,
    then no-ops. Spaces at a run end are invisible (the line ends there or the next run continues)."""
    room = cap - len(b)
    out = bytearray(b)
    need = max(0, en_chars - chars(b))
    sp = min(room, need)
    out += b' ' * sp
    out += bytes([PAD]) * (room - sp)
    return bytes(out)

def respeed(data, off, en_len, new_bytes):
    """If the run is directly preceded by a speed opcode (02 xx), scale xx so the Korean run takes as long as the
    English one: xx' = round(xx * en_chars / ko_chars). Returns True if changed. Leftover is padded by pad()."""
    if off >= 2 and data[off - 2] == 0x02 and 1 <= data[off - 1] <= 0x20:
        global _ERR
        sp = data[off - 1]; k = max(1, chars(new_bytes))
        want = sp * en_len / k + _ERR / k                      # carry the rounding error to the next runs
        ns = max(1, min(0x30, int(want + 0.5)))
        _ERR = (want - ns) * k
        data[off - 1] = ns
        return ns
    return None

def fill(data, off, b, cap, en_len, script_start):
    """Write a Korean run in place keeping the English duration: speed scaling + waits + no-ops."""
    ns = respeed(data, off, en_len, b)
    if ns is not None:
        data[off:off + cap] = bytes(b) + bytes([PAD]) * (cap - len(b))   # duration already matched by speed
    else:
        nxt = data[off + cap] if off + cap < len(data) else 0
        if nxt >= 0x20:              # the line continues with the next run: trailing spaces would show
            data[off:off + cap] = bytes(b) + bytes([PAD]) * (cap - len(b))
        else:
            data[off:off + cap] = pad(b, cap, en_len, speed_at(bytes(data), off, script_start))
