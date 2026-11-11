import re
ARGS = {0x16: 1, 0x02: 1, 0x03: 1, 0x11: 1, 0x05: 2, 0x0b: 3, 0x07: 1, 0x08: 1, 0x09: 1}
VOICE = re.compile(rb'(?:(?<=\x0b)\x09([\x30-\x5f].)\x0a?|\x09([\x30-\x5f].)\x0a)', re.S)

def tokens(seg):
    i = 0; n = len(seg)
    while i < n:
        b = seg[i]
        if b >= 0x80:
            if i + 1 < n: yield ('c', b << 8 | seg[i + 1])
            i += 2
        elif b >= 0x20: yield ('a', chr(b)); i += 1
        elif b == 0x01: yield ('nl',); i += 1
        elif b == 0x04: yield ('a', ' '); i += 1
        elif b == 0x00: i += 1
        else:
            yield ('op', b); i += 1 + ARGS.get(b, 0)

def blocks(data):
    ms = list(VOICE.finditer(data)); out = []
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else min(len(data), m.end() + 0x600)
        out.append((m.start(), (m.group(1) or m.group(2)).hex(), data[m.end():end]))
    return out
