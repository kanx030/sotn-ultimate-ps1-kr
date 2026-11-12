"""ST0 prologue (PS1 script) Korean text. Each entry replaces one text run in place: (file offset, original, korean).
Hangul = 2 bytes (16px), ASCII = 1 byte (8px). Korean must fit the run's byte length (padded with spaces)."""
import json, os

RUNS = [
    # Richter
    (0x29f5, "Die monster.", "죽어라 괴물아."),
    (0x2a06, "You don't belong", "여긴 네가 있을"),
    (0x2a19, "in this world!", "세상이 아니다!"),
    # Dracula
    (0x2a3a, "It was not by my", "내가 다시 육신을"),
    (0x2a4d, "hand that I am once", "얻은 건 내 손으로"),
    (0x2a63, "again given flesh.", "한 일이 아니다."),
    (0x2a78, "I was called here", "날 이곳에 "),
    (0x2a8c, "by ", "부른 건 "),
    (0x2a93, "humans ", "나에게 "),
    (0x2a9e, "who", " "),
    (0x2aa4, "wish to pay me", "경배하려는"),
    (0x2ab5, "tribute.", "인간들이다"),
    # Richter
    (0x2acc, "Tribute!?!", "경배라고?"),
    (0x2add, "You steal men's", "너는 사람들의 "),
    (0x2aef, "souls ", "영혼을 훔쳐 "),
    (0x2afb, "and make them", "노예로"),
    (0x2b0d, "your slaves!", "삼고 있다!"),
    # Dracula
    (0x2b26, "Perhaps the same", "어쩌면 같은 말을"),
    (0x2b39, "could be said", "모든 종교에도"),
    (0x2b49, "of", "할"),
    (0x2b4d, " all religions...", " 수 있겠지..."),
    # Richter
    (0x2b6d, "Your words are as", "네 말은"),
    (0x2b83, "empty as your soul!", "네 영혼만큼 공허하구나!"),
    (0x2b9b, "Mankind ill needs a", "인류에게 너 같은"),
    (0x2bb7, "savior such as you!", "구세주는 필요 없다!"),
    # Dracula
    (0x2bd9, "What is a man?", "인간이란 무엇인가?"),
    (0x2bf0, "A miserable little", "비참하고 하찮은"),
    (0x2c05, "pile of secrets.", "비밀 덩어리일 뿐"),
    (0x2c1c, "But enough ", "잡담은 이쯤 "),
    (0x2c29, "talk...", "하지..."),
    (0x2c33, "Have at you!", "덤벼라!"),
]

_rev = None
def _map():
    global _rev
    if _rev is None:
        m = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'work', 'kmap.json'), encoding='utf-8'))['map']
        _rev = {v: int(k, 16) for k, v in m.items() if len(v) == 1}
    return _rev

PAD = bytes([0x0D])   # cutscene engine opcode 13 = no-op (jump table entry is the read loop)
FULLWIDTH = {'．': 0x8144, '？': 0x8148, '！': 0x8149, '”': 0x8168, '（': 0x8169, '）': 0x816A, '　': 0x8140, '１': 0x8250}

def enc(s):
    r = _map(); out = bytearray()
    for ch in s:
        if ch in FULLWIDTH:
            out += FULLWIDTH[ch].to_bytes(2, 'big')
        elif ch in r:
            out += r[ch].to_bytes(2, 'big')
        elif '가' <= ch <= '힣':
            import fontext
            fontext.ensure(ch)
            out += fontext.code_of(ch).to_bytes(2, 'big')
        elif ord(ch) < 0x7f:
            out.append(ord(ch))
        else:
            raise KeyError('no glyph for %r' % ch)
    return bytes(out)

def width(s):
    return sum(8 if ord(c) < 0x7f else 16 for c in s)

def patch_runs(data, runs, terminate=False):
    """Replace byte runs in place. runs: (offset, original bytes|str, korean, cap). If terminate, write a NUL after."""
    data = bytearray(data)
    for off, en, ko, cap in runs:
        en = en.encode('latin1') if isinstance(en, str) else en
        assert data[off:off + len(en)] == en, (hex(off), en)
        b = enc(ko)
        assert len(b) <= cap, (ko, len(b), cap)
        if terminate:
            data[off:off + cap + 1] = b + b'\0' * (cap + 1 - len(b))
        else:
            data[off:off + len(en)] = b + PAD * (len(en) - len(b))
    return bytes(data)

def cutscene_strings():
    return [ko for _, _, ko in RUNS]

def patch(st0):
    st0 = bytearray(patch_crawl(st0))
    import build, repack
    runs = []
    for off, en, ko in RUNS:
        en = en.encode()
        assert st0[off:off + len(en)] == en, (hex(off), en)
        runs.append((off, len(en), ko))
    st0 = bytearray(repack.repack(st0, None, runs, build.bank().encode))
    return bytes(st0)

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    bad = []
    for off, en, ko in RUNS:
        try:
            b = enc(ko); ok = len(b) <= len(en)
        except KeyError as e:
            b = b''; ok = False; bad.append(str(e))
        print('%5x %2d/%2d %3dpx %s %s' % (off, len(b), len(en), width(ko), 'OK ' if ok else 'BAD', ko))
    print('missing:', bad)

# Opening crawl (after the Dracula fight): drawn by a different routine (GetGlyph 0x801B17F8 -> glyph API).
# Padding must be ASCII space there (0x0D would draw garbage). Lines are centred by the game.
CRAWL = [
    (0x2c58, "It was Richter Belmont,", "전설의 뱀파이어 헌터"),
    (0x2c71, "the legendary vampire hunter,", "리히터 벨몬드는 "),
    (0x2c90, "who succeeded in finally ending", "마침내 어둠의 사제 샤프트에 의해"),
    (0x2cb1, "the menace of Count Dracula,", "무덤에서 되살아난 "),
    (0x2ccf, "Lord of the Vampires who had been", "흡혈귀의 군주, 드라큘라 백작의"),
    (0x2cf2, "brought back from the grave by", "위협을 끝내는 데"),
    (0x2d12, "the dark priest Shaft.", "성공했다."),
    (0x2d2a, "However, one night 4 years later,", "그러나 4년 후의 어느 밤,"),
    (0x2d4d, "under the glare of a full moon,", "보름달이 환하게 빛나던 때,"),
    (0x2d6e, "Richter mysteriously vanished.", "리히터는 홀연히 자취를 감췄다."),
    (0x2d8e, "With no idea of where to begin", "그의 동생 마리아 라네드는"),
    (0x2dae, "her search, Maria Renard", "어디서부터 찾을지도 모른 채"),
    (0x2dc8, "set out to look for him.", "그를 찾아 길을 떠났다."),
    (0x2de2, "It was then that fate intervened.", "바로 그때, 운명이 개입했다."),
    (0x2e05, "Castlevania, the castle of Dracula,", "백 년에 한 번 나타난다는"),
    (0x2e2a, "which is rumored to appear once", "드라큘라의 성. "),
    (0x2e4b, "every century, suddenly", "악마성이 마치 그녀에게"),
    (0x2e64, "materialized from out of the mist", "길을 알려 주려는 듯"),
    (0x2e87, "as if to show her the way.", "안개 속에서 나타났다."),
    (0x2ea3, "Meanwhile, powerful forces were", "한편, 강대한 힘들이 "),
    (0x2ec4, "struggling for the soul of", "알카드라는 한 사내의"),
    (0x2ee0, "a man named Alucard.", "영혼을 노리고 있었다."),
    (0x2ef6, "The very same Alucard who had", "그 알카드는 일찍이"),
    (0x2f15, "teamed up with Trevor Belmont to", "트레버 벨몬드와 손을 잡고"),
    (0x2f37, "battle his immortal father,", "불멸의 아버지인"),
    (0x2f54, "Count Vlad Tepes Dracula.", "드라큘라와 싸웠던 자다."),
    (0x2f6f, "Alucard, in order to purge the world", "알카드는 저주받은 자신의 피로부터"),
    (0x2f95, "of his own cursed blood line,", "세상을 지키기 위해"),
    (0x2fb4, "had submerged his vampiric powers", "흡혈귀의 힘을 봉인하고"),
    (0x2fd7, "and entered into what was supposed", "영원히 깨지 않을"),
    (0x2ffb, "to be an eternal slumber.", "잠에 들었을 터였다."),
    (0x3016, "But now, he is awake and aware of", "그러나 이제 그는 눈을 떴고,"),
    (0x3039, "the evil once again at work", "고향 땅에서 다시금 꿈틀대는"),
    (0x3055, " in his homeland.", "악을 느끼고 있다"),
    (0x3068, "The time has once again come for", "선과 악의 세력이 다시 한 번"),
    (0x308a, "the forces of Good and Evil to", "태고의 싸움을 벌일 때가 왔다."),
    (0x30aa, "engage in their ancient battle.", "그리고 지금, 저마다의 생각을 품은"),
    (0x30cb, "Dracula's castle beckons for you...", "숙명의 영혼들이 드라큘라 성으로 모여든다."),
    (0x30f0, "And no man can say who shall", "어둠 속에 떠오른 달만이"),
    (0x310e, "emerge victorious.", "진실을 알고 있는 것일까."),
]

CRAWL_CENTER = 54          # mean centre of the English lines, in 4-px VRAM units (base 0x200)
import addrmap
CRAWL_X0 = addrmap.ovl('ST/ST0/ST0.BIN', 0x801B16AC) - 0x80180000   # v1.2 0x801B16AC: ori v0,zero,0x216 (x of the first line; later lines: "01/02 xx" arg)

def crawl_units(b):
    """advance of an encoded crawl line: every glyph (Hangul or ASCII) 3 units = 12 px, a space 2 units."""
    u = i = 0
    while i < len(b):
        if b[i] >= 0x80: u += 3; i += 2
        else: u += 2 if b[i] == 0x20 else 3; i += 1
    return u

def crawl_slots(st0):
    """(text offset, text cap, x-arg offset or None for the first line) per CRAWL line."""
    out = []
    for off, en, ko in CRAWL:
        eb = en.encode()
        assert st0[off:off + len(eb)] == eb, (hex(off), en)
        if off == CRAWL[0][0]:
            out.append((off, len(eb), None))
        elif en.startswith(' ') and st0[off - 1] in (1, 2):   # " in his homeland.": the space IS the x arg
            out.append((off + 1, len(eb) - 1, off))
        else:
            assert st0[off - 2] in (1, 2), hex(off)
            out.append((off, len(eb), off - 1))
    return out

def patch_crawl(st0):
    """Left-aligned crawl, repacked: the crawl is one stream (text, then "01/02 x" before each next line, 00 at the
    end), so lines are written back to back and a long line can borrow bytes from short ones. Every line gets the
    same x, chosen so the widest Korean line is centred."""
    st0 = bytearray(st0)
    slots = crawl_slots(st0)
    start = slots[0][0]
    end = slots[-1][0] + slots[-1][1]
    assert st0[end] == 0, hex(end)
    ops = [None] + [st0[xa - 1] for _, _, xa in slots[1:]]
    assert all(o in (1, 2) for o in ops[1:])
    encs = [enc(ko).strip(b' ') for _, _, ko in CRAWL]
    x = max(0, int(CRAWL_CENTER - max(crawl_units(b) for b in encs) / 2 + 0.5))
    assert st0[CRAWL_X0:CRAWL_X0 + 4] == bytes.fromhex('16020234'), st0[CRAWL_X0:CRAWL_X0 + 4].hex()
    st0[CRAWL_X0:CRAWL_X0 + 2] = (0x200 + x).to_bytes(2, 'little')
    out = bytearray()
    for op, b in zip(ops, encs):
        if op is not None: out += bytes([op, x])
        out += b
    out.append(0)
    assert len(out) <= end + 1 - start, ('opening crawl too long', len(out), end + 1 - start)
    st0[start:end + 1] = out + bytes(end + 1 - start - len(out))
    return bytes(st0)
