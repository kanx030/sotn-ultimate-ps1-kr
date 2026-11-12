"""Ending staff roll (SEL.BIN / SELRIC2.BIN) -> Korean headers and roles; people's names stay romanised.

The roll is one byte stream at SEL 0xBC54 (0x8018BC54, started by lui/addiu at 0x801C0B44) up to its 00 end
(0xC403; the pointer table at 0xC404 follows). Engine 0x801C0CB4: 01/02/03 <x> = new line (x in halfword
units, 3 per character), 00 = end, a byte >= 0x80 + next byte = 2-byte code sent to the glyph API
(0x8003C800 -> our Korean font lookup), other bytes = ASCII (converted to SJIS by 0x801C09C8). Every
character, ASCII or Korean, advances the cursor by 3 halfwords (12 px), so Korean lines are re-centred
with x = round(CENTRE - 1.5 * chars).

    data = credits.patch(data)       # SEL.BIN (build: called from seltext.patch)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

START, END = 0xBC54, 0xC403          # END = the 00 terminator
CENTRE = 39.0

# English line text -> Korean (lines not listed stay as they are)
KO = {
    'CASTLEVANIA': '악마성 드라큘라',
    'SYMPHONY OF THE NIGHT': '월하의 야상곡',
    '-Cast-': '-출연-',
    '-Staff-': '-제작진-',
    '-Producer & Director-': '-제작 & 감독-',
    '-Assistant Director-': '-조감독-',
    '-Localization A.D.-': '-현지화 조감독-',
    '-Programers-': '-프로그래머-',
    '-Designers-': '-디자이너-',
    '-Scenario Writers-': '-시나리오-',
    '-Sound Staff-': '-사운드 스태프-',
    '(MUSIC/SOUND EFFECTS)': '(음악/효과음)',
    '(PROGRAM/SOUND EFFECTS)': '(프로그래머/효과음)',
    'IMOHORE IMAI(MIXER)': 'IMOHORE IMAI(음향)',
    '-Musicians-': '-연주-',
    '(ELECTRIC GUITAR)': '(전자 기타)',
    'KAHORI YAMANE(VOCAL)': 'KAHORI YAMANE(보컬)',
    '-Voice Coordinatar-': '-음성 코디네이터-',
    '-Product Design-': '-제품 디자인-',
    '-Character Design  ': '-인물 디자인',
    '    & Illustrations-': '& 일러스트-',
    '-Ending Theme-': '-주제가-',
    'Produced by': '제작',
    'Music written by': '작곡',
    'Arranged by': '편곡',
    'Recorded by': '녹음',
    'Mixed by': '음향 조정',
    '(LEAD VOCAL/BACK CHORUS)': '(리드 보컬/코러스)',
    'JEFF LORBER(KEYBOARDS)': 'JEFF LORBER(키보드)',
    'RIKA MURANAKA(KEYBOARDS)': 'RIKA MURANAKA(키보드)',
    'NATE PHILLIPS(BASS)': 'NATE PHILLIPS(베이스)',
    'JOHN ROBINSON(DRUMS)': 'JOHN ROBINSON(드럼)',
    'MICHAEL TOMPSON(GUITAR)': 'MICHAEL TOMPSON(기타)',
    'GERALD ALBRIGHT(SAX)': 'GERALD ALBRIGHT(색소폰)',
    'LOUIS CONTE(PERCUSSION)': 'LOUIS CONTE(퍼커션)',
    '-Special Thanks-': '-도움을 주신 분들-',
    '-Translation-': '-번역-',
    '-VO Talent Booking-': '-성우 담당-',
    '-Recording Studio-': '-녹음실-',
    '-Executive Producer-': '-제작 총지휘-',
}


def parse(d):
    i, lines = START, []
    while d[i] != 0:
        b = d[i]
        if b in (1, 2, 3):
            lines.append([b, d[i + 1], b'']); i += 2; continue
        n = 2 if b >= 0x80 else 1
        lines[-1][2] += bytes(d[i:i + n]); i += n
    assert i == END, hex(i)
    return lines


def patch(data):
    d = bytearray(data)
    if d[START:START + 13] != b'\x01\x16CASTLEVANIA':
        return bytes(d)                              # not the US roll (already patched / other layout)
    from st0text import enc
    out = bytearray()
    for op, x, t in parse(d):
        try:
            en = t.decode('ascii')
        except UnicodeDecodeError:
            en = None
        if en in KO:
            ko = KO[en]
            t = enc(ko)
            x = max(0, int(round(CENTRE - 1.5 * len(ko))))
        out += bytes([op, x]) + t
    out.append(0)
    cap = END + 1 - START
    assert len(out) <= cap, (len(out), cap)
    d[START:END + 1] = out + bytes(cap - len(out))
    return bytes(d)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    u = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'U', 'ST', 'SEL', 'SEL.BIN'), 'rb').read()
    p = patch(u)
    used = len(p[START:END + 1].rstrip(b'\0')) + 1
    print('credits: %d of %d bytes' % (used, END + 1 - START))
    print([k for k in KO if k.encode() not in u[START:END]])
