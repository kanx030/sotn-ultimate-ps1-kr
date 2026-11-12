"""Write work/trans/extra_<NAME>.json sheets: overlay English that the cutscene sheets (extract_scripts.py) miss.
python extragen.py      (then: python extraapply.py  to check every sheet)

Paths found (see extraapply.py):
  api      message boxes (entity 0x0E: [w px, h px] header + text, 01 = new line, 81 44 = '.'), relic-orb
           'Obtained ' prefix, librarian enemy descriptions ('@' = new line) and shop item descriptions.
           All go through the stage char blitter -> glyph API 0x8003C800 (a-z/A-Z/space -> SJIS, else 2 bytes).
  menu8    LIB shop / tactics / sound-test / enemy-list labels (engine A: ASCII-0x20, 00 = space, FF 00 end).
  ascii8   LIB main menu + ATT/DEF (0x801B191C raw ASCII cells; libfix.py replaces it with a Korean bitmap blit).
           menu8 items with 'want' do not fit in place: libfix.py moves them into free LIB space.
  cutscene SEL ending, MAR (Maria) and a missed DAI run. SEL/MAR use a variant of the cutscene engine
           (char in a1, SEL 0x801C0440 / MAR 0x8018C6A8) that build.patch_cutscene does not hook yet.
"""
import os, sys, re, json, struct, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
from base import U
TR = os.path.join(ROOT, 'work', 'trans')
B = 0x80180000


def rd(f):
    return open(os.path.join(U, *f.split('/')), 'rb').read()


def words(x):
    n = len(x) // 4
    return struct.unpack_from('<%dI' % n, x)


def dec2(b, nl=0x01):
    s, i = '', 0
    while i < len(b):
        c = b[i]
        if c >= 0x80:
            s += b[i:i + 2].decode('cp932', 'replace'); i += 2
        else:
            s += '\n' if c == nl else chr(c); i += 1
    return s


# ---------------------------------------------------------------- message boxes (api)
MSG_KO = {
    'Mist could pass．': '안개라면 간다.',
    'I have nothing to do\nwith this wall．．．': '이 벽은 나와는\n상관없다…',
    'Magically sealed．': '마법으로 봉인됨.',
    'Something appeared near\nto the wooden bridge．': '나무 다리 근처에\n무언가가 나타났다.',
}


def msgboxes(x):
    """(code_off, string_off) for 'lui v0,0x8018; addiu v0,v0,lo; sw v0,124(sX)' (entity 0x0E label)."""
    W = words(x); out = []
    for i in range(len(W) - 3):
        w = W[i]
        if w >> 26 == 15 and (w & 0xFFFF) == 0x8018:
            rt = (w >> 16) & 31
            for j in range(i + 1, i + 4):
                v = W[j]
                if v >> 26 == 9 and (v >> 21) & 31 == rt:
                    va = B + (v & 0xFFFF) - (0x10000 if v & 0x8000 else 0)
                    for k in range(j + 1, j + 4):
                        u = W[k]
                        if u >> 26 == 43 and (u & 0xFFFF) == 124 and (u >> 16) & 31 == (v >> 16) & 31:
                            out.append(va - B)
                    break
    return sorted(set(out))


# ---------------------------------------------------------------- relic orb prefix (api)
OBTAINED_KO = '마도기: '


def obtained(x):
    W = words(x)
    ptrs = {w - B for w in W if B <= w < B + len(x)}
    return [m.start() for m in re.finditer(rb'Obtained \x00', x) if m.start() in ptrs]


# ---------------------------------------------------------------- LIB enemy descriptions (api, '@' = new line)
LIB_DESC = {
    0x2bb94: '방패와 창을 든 해골.\n요충지를 지킨다.',
    0x2bbcc: '가까이 가면 위험한\n무서운 죽음의 영혼.',
    0x2bc04: '시체를 조종하는 빛이\n본체이다.',
    0x2bc3c: '여러 동물의 뼈로 만든\n인조 짐승.',
    0x2bc70: '해골 짐승을 데리고 다니는\n추적자의 해골.',
    0x2bca8: '증오가 사라지지 않는\n더럽혀진 영혼.',
    0x2bcd8: '실체가 없는 유령.\n성스러운 무기만 통한다.',
    0x2bd10: '파리가 아닌 인간을 먹는\n거대한 파리지옥.',
    0x2bd48: '강에 사는 명랑한 괴물.\n치킨 맛이 난다.',
    0x2bd7c: '리히터 벨몬드를 찾는\n뱀파이어 헌터.',
    0x2bdac: '사람 얼굴 열매가 풍성해\n늘 미소 짓고 있다.',
    0x2bde8: '성의 미친 정원사.\n정원을 망치면 죽인다.',
    0x2be24: '해골 병사의 대장.\n결투에서 뼈가 부러졌다.',
    0x2be60: '분노한 악마.\n말 그대로 불타는 남자.',
    0x2be8c: '매우 가치가 높은\n골동품.',
    0x2beb8: '살아 있는 석상.\n성의 방범 장치.',
    0x2bef4: '뱀파이어 헌터. 전설의\n4마수. 리히터를 찾는다.',
    0x2bf2c: '발라키아의 영주.\n알카드의 아버지.',
    0x2bf54: '드라큘라의 사제.',
    0x2bf70: '드라큘라의 친구.',
    0x2bf8c: '상급 아머 로드.',
    0x2bfa4: '명계를 지배하려는\n마법 생물.',
    0x2bfd8: '희귀한 새.\n사람을 보면 도망친다.',
    0x2c000: '뱀파이어 헌터의 달인.',
    0x2c018: '어린 마녀.',
    0x2c030: '얼음 정령.\n갈라모스의 부하.',
    0x2c060: '지옥의 사형 집행인.',
    0x2c078: '파리의 왕 베르제브브.',
    0x2c094: '사이파로 변장한 좀비.',
    0x2c0b4: '장난꾸러기 꼬마 악마.',
    0x2c0d0: '트레버로 변장한 좀비.',
    0x2c0f0: '그랜트로 변장한 좀비.',
    0x2c110: '강한 전사들의 몸을\n이어 붙여 만들었다.',
    0x2c144: '뱀 머리의 마녀.\n눈빛으로 돌로 만든다.',
    0x2c174: '비너스 위드의 상위종.\n악마의 피를 먹었다.',
    0x2c1a4: '고대 이집트의 미라.',
    0x2c1c0: '지옥의 흉측한 악마.',
    0x2c1dc: '갑옷을 두른 전투 짐승.',
    0x2c1f8: '불꽃 악마.',
    0x2c208: '사악한 변이 문어.',
    0x2c220: '긴 혀로 피를 빠는\n원시적인 흡혈 생물.',
    0x2c260: '와그를 탄 해골.',
    0x2c27c: '뛰어올라 공격하는 해골.',
    0x2c29c: '천사 궁수.\n고트족 아말라릭을 죽였다.',
    0x2c2c8: '바위를 던지는\n갑옷 기사.',
    0x2c2e8: '화염구를 뿜는 늑대.',
    0x2c304: '움직이는 거대한\n용의 해골.',
    0x2c328: '플리 맨이 조종하는 비룡.',
    0x2c348: '무시무시한 광선\n무기를 쓴다.',
    0x2c368: '반은 인간, 반은 소.',
    0x2c384: '플리 맨이 탄 백룡.',
    0x2c3a8: '거대 흡혈 박쥐.',
    0x2c3bc: '액체 생물.\n검은 표범 모습을 한다.',
    0x2c3ec: '반은 인간, 반은 늑대.',
    0x2c408: '무서울 만큼 정확한 궁수.',
    0x2c428: '무기 던지기의 달인.',
    0x2c448: '변이된 곤충.\n마법사에게만 보인다.',
    0x2c478: '반으로 잘려도\n공격해 오는 좀비.',
    0x2c4a8: '폭탄을 던지는\n갑옷 기사.',
    0x2c4c8: '제 해골을 영원히\n쫓아다니는 해골.',
    0x2c4f4: '무수한 독 씨앗을 품었다.',
    0x2c514: '심장 없는 양철 인간',
    0x2c528: '쉬무라 불리는 괴물.',
    0x2c54c: '악몽 같은 괴물.\n많은 것이 합쳐졌다.',
    0x2c578: '뇌를 찾는 꼬챙이 인간.',
    0x2c59c: '겁쟁이 사자.',
    0x2c5b0: '사람의 피로 키워졌다.',
    0x2c5cc: '죽은 자의 악령이\n깃든 묘비.',
    0x2c600: '여자 악마.\n남자의 꿈에 들어온다.',
    0x2c628: '마법을 쓰는 흡혈귀.\n성의 위쪽을 지배한다.',
    0x2c660: '어인의 우두머리.',
    0x2c674: '지옥의 파수견.',
    0x2c688: '번개를 다루는 악마.\n지옥의 음악가라 불린다.',
    0x2c6c8: '점액질 젤로\n만들어진 괴물.',
    0x2c6f4: '까마귀의 마왕.',
    0x2c70c: '원반을 쓰는\n갑옷 기사.',
    0x2c730: '거인 형제.\n거대한 쇠망치를 쓴다.',
    0x2c75c: '거인 형제.\n구르카 칼을 휘두른다.',
    0x2c784: '거인 형제의 장남.\n거대한 단검 두 자루를 쓴다.',
    0x2c7b8: '세일럼의 유령 마녀.',
    0x2c7d4: '무덤을 뒤지는 자.\n지식이 풍부하다.',
    0x2c808: '마법을 쓰는 작은 악마.\n동료 악마를 부른다.',
    0x2c840: '어인 수호자.',
    0x2c858: '망토를 두른\n수수께끼의 검사.',
    0x2c878: '영원히 싸움을 찾는\n피에 굶주린 망자 기사.',
    0x2c8b4: '해골 사제들이 메고 다니는\n해골 사당.',
    0x2c8ec: '모습을 바꾸는 수인.',
    0x2c90c: '소 머리의 괴물.',
    0x2c924: '여자의 머리에\n새의 몸을 가진 괴물.',
    0x2c954: '불장난을 좋아하는 악마',
    0x2c96c: '묘지기.\n맨손 격투의 달인.',
    0x2c998: '표범 수인의 해골.',
    0x2c9b0: '쌍검술의 달인.',
    0x2c9d4: '젤로 만든 괴물.',
    0x2c9ec: '거대한 해골.',
    0x2ca00: '말・사자・독수리의 합성수.',
    0x2ca20: '도끼와 방패를 든\n플리 맨.',
    0x2ca48: '봉인되어도 검을\n휘두르는 소드 로드.',
    0x2ca78: '중무장한 기사.\n길들인 올빼미로 공격한다.',
    0x2caac: '움직이는 진흙 인형.',
    0x2cac4: '보이지 않는 사냥꾼 정령.',
    0x2cae0: '신화 속 바다 괴물.',
    0x2cafc: '나기나타를 든 해골.',
    0x2cb1c: '사악한 마검.\n폴터가이스트를 일으킨다.',
    0x2cb50: '특별히 길들인 군용 거위를\n탄 플리 맨.',
    0x2cb84: '가시 쇠도리깨를 든\n해골.',
    0x2cbb0: '오래전 죽은\n푸른 까마귀의 영혼.',
    0x2cbd4: '고기를 먹는 까마귀.',
    0x2cbec: '거대한 해골 영혼.',
    0x2cc04: '고대 무기의 책.',
    0x2cc20: '얼음을 다루는 여자 정령.',
    0x2cc40: '동굴에 사는 개구리.',
    0x2cc58: '머리 없는 해골.\n레이피어를 쓴다.',
    0x2cc80: '갑옷 경비병.\n험한 곳에서 강하다.',
    0x2ccac: '중무장한\n망자 전사.',
    0x2ccd0: '악마의 세례로\n거대해진 두꺼비.',
    0x2cd00: '대검을 든 기사.',
    0x2cd20: '몸 없이 고통받는 영혼이\n실체화한 것.',
    0x2cd58: '느리게 나는 해골 전사.',
    0x2cd78: '초급 마법서.',
    0x2cd98: '나기나타를 든\n갑옷 전사.',
    0x2cdbc: '움직이는 원숭이 해골.\n나무통을 던진다.',
    0x2cdec: '스킬라에 기생하는 뱀.',
    0x2ce08: '처형된 병사의 머리.\n복수를 노린다.',
    0x2ce3c: '성의 영향으로\n변이된 올빼미.',
    0x2ce74: '모습을 바꾸는 악마.',
    0x2ce8c: '희게 바랜 용의\n두개골로 만든 기둥.',
    0x2cebc: '활을 든 해골 궁수.',
    0x2cee4: '불과 얼음의 악마.\n싸움은 내키지 않는 듯.',
    0x2cf14: '중무장한 도끼 기사.',
    0x2cf30: '변이 식물.\n씨앗에 석화된다.',
    0x2cf50: '쇠공을 든\n중무장 기사.',
    0x2cf7c: '메두사의 머리카락.\n돌로 만든다.',
    0x2cfa0: '소총을 든 해골.',
    0x2cfc4: '쌍검술의 초보자.',
    0x2cfe8: '메두사의 머리카락.',
    0x2d000: '인간을 닮은 괴생물.\n벼룩처럼 뛰어오른다.',
    0x2d034: '구역질 나는 쌍두 짐승.\n어느 쪽이 머리일까?',
    0x2d068: '마법 창을 든 악마.',
    0x2d088: '지옥의 악마 인형.',
    0x2d0a4: '하급 불꽃 유령.',
    0x2d0c0: '불을 뿜는 비행 악마.',
    0x2d0e0: '면도날 같은 잎을 지닌\n식물.',
    0x2d104: '부메랑을 쓰는 해골.',
    0x2d124: '귀신 들린 위자판.',
    0x2d13c: '뼈를 던지는 해골.',
    0x2d158: '300년 전 파견된\n동방 교회의 병사.',
    0x2d190: '하급 도끼 기사.',
    0x2d1a8: '네 발 달린 해골.\n독을 흘린다.',
    0x2d1d0: '화염구를 뿜는 어인.\n어인 중 가장 크다.',
    0x2d208: '사나운 해골 검사.',
    0x2d228: '성 입구를 지키는\n늑대.',
    0x2d250: '마법으로 움직이는 해골.',
    0x2d270: '전설의 괴물.\n침입자를 모두 공격한다.',
    0x2d2a4: '갓 죽은 시체.\n마법으로 움직인다.',
    0x2d2cc: '부서지지 않는 회전 해골.',
    0x2d2ec: '흡혈 박쥐.\n악의 하수인으로 두려워한다.',
    0x2d318: '피를 머금은 뼈로\n되살아난다.',
    0x2d33c: '1792년(5년 전)\n리히터에게 쓰러졌다.',
}
LIB_DESC_RANGE = (0x2bb94, 0x2d370)

# shop item descriptions (api, drawn by 0x801B15A0 with a 252 px buffer)
LIB_SHOP = {
    0x2d560: '소울 스틸이 적혀 있다',
    0x2d57c: '테트라 스피릿이 적혀 있다',
    0x2d59c: '헬파이어가 적혀 있다',
    0x2d5b8: '서먼 스피릿이 적혀 있다',
    0x2d5d8: '다크 메타모포시스가 적혀 있다',
    0x2d5fc: '드라큘라 성의 대략적인 지도',
}

# engine A strings (None = keep English but in upper case, which the Korean 8x8 sheet can still show)
LIB_MENU8 = {
    0x2d4fc: '장비 안 함', 0x2d50c: '장비 중', 0x2d518: '개수',
    0x2d660: '언록 주얼', 0x2d670: '마법서 5', 0x2d680: '마법서 4', 0x2d690: '마법서 3',
    0x2d6a0: '마법서 2', 0x2d6b0: '마법서 1', 0x2d6c0: '성 지도',
    # tactics (Saturn enemy_ko / menu_ko names; the ones that do not fit their slot get 'want' and are
    # relocated by libfix.py)
    0x2d70c: '드라큘라 백작', 0x2d71c: '샤프트', 0x2d728: '갈라모스', 0x2d734: '다크윙 배트',
    0x2d744: '아크모단 2세', 0x2d750: '도플갱어40', 0x2d760: '레서 데몬', 0x2d770: '크리처', 0x2d780: '메두사',
    0x2d788: '리히터 벨몬드', 0x2d79c: '케르베로스', 0x2d7a8: '사신', 0x2d7b0: '트레버&그랜트&사이파',
    0x2d7c4: '카라스만', 0x2d7d0: '서큐버스', 0x2d7dc: '베엘제붑', 0x2d7e8: '히포그리프',
    0x2d7f4: '슬로그라&가이본', 0x2d804: '스킬라', 0x2d80c: '미노타우로스&늑대인간', 0x2d820: '그랑팔룬',
    0x2d82c: '도플갱어10', 0x2d83c: '올록스', 0x2d844: '드라큘라',
    # shop table 0x8018181C (JP katakana neighbours are never shown in US)
    0x2d920: '액스',
    # enemy list labels
    0x2d99c: '-', 0x2d9a4: '타격', 0x2d9ac: '참격', 0x2d9b4: '저주', 0x2d9bc: '독', 0x2d9c4: '석화',
    0x2d9cc: '물', 0x2d9d4: '얼음', 0x2d9dc: '번개', 0x2d9e4: '불', 0x2d9ec: '어둠', 0x2d9f4: '신성',
    0x2d9fc: '흡수', 0x2da04: '약점', 0x2da10: '무효', 0x2da18: '강함', 0x2da28: '번호', 0x2da30: '아이템', 0x2da3c: '경험',
    # sound test
    0x2daa4: '나는 바람', 0x2dab4: '변신 3', 0x2dac8: '검은 연회', 0x2dad8: '피날레',
    0x2dae8: '변신 2', 0x2dafc: '피의 인연', 0x2db10: '죽음의 곡', 0x2db20: '천상의 문',
    0x2db34: '심연의 문', 0x2db48: '비극의 왕자', 0x2db5c: '헤매는 유령', 0x2db70: '마법의 연회',
    0x2db84: '저주의 땅', 0x2db90: '망령의 춤', 0x2dba0: '사라진 그림', 0x2dbb0: '정적',
    0x2dbbc: '무지개 묘지', 0x2dbd0: '버려진 갱도', 0x2dbe0: '수정 물방울', 0x2dbf4: '신들의 진혼곡',
    0x2dc0c: '축복의 땅', 0x2dc24: '하인들의 축제', 0x2dc3c: '성령의 문', 0x2dc54: '목각 파르티타',
    0x2dc6c: '안개의 탑', 0x2dc7c: '대리석 홀', 0x2dc8c: '황금의 춤', 0x2dc9c: '드라큘라 성',
    0x2dcb0: '기도', 0x2dcb8: '월광 녹턴', 0x2dccc: '환상의 춤', 0x2dce0: '서곡', 0x2dcec: '변신 1',
}

# LIB main menu (ascii8: first byte = column)
LIB_ASCII8 = {
    0x2d3b9: '보석 팔기', 0x2d3c5: '나가기', 0x2d3cd: '사운드 테스트', 0x2d3d9: '적 목록',
    0x2d3e5: '전술', 0x2d3f1: '아이템 구매',
    0x2d4f0: '공격', 0x2d4ec: '방어',          # ATT / DEF (table 0x80181528; Saturn game_text labels)
}

# ---------------------------------------------------------------- cutscene runs
SEL_KO = {
    0xb32e: '인간은 끝없이', 0xb342: '싸우지만, ', 0xb350: '그것은', 0xb35c: '살아남기 위한 필사의', 0xb373: '싸움이다.', 0xb386: '아마 그는', 0xb39a: '싸움 속의 삶을', 0xb3ae: '택했지. ', 0xb3ba: '그것이', 0xb3c7: '그가 아는 유일한', 0xb3da: ' ', 0xb3df: '길.', 0xb3ea: '아버지, 당신처럼', 0xb3ff: '그도 파멸의 길을', 0xb414: '택했던 거요...', 0xb42a: '잘 있거라,', 0xb436: ' 나의', 0xb443: '고향아.', 0xb44c: ' 두 번 다시', 0xb45a: '네 아름다움을', 0xb471: '볼 일은 없으리라.', 0xb4a3: '무사했나 보군.', 0xb4c5: '알카드!', 0xb4d2: '리히터', 0xb4db: '는요?', 0xb4f0: '미안하다...', 0xb509: '그', 0xb50d: '래요..', 0xb518: '그를 막아줘서', 0xb52a: '고마워요...', 0xb53e: '이것도 운명이라고', 0xb554: '생각하세요?', 0xb57e: '그럼 네 여행도', 0xb593: '끝난 건가?', 0xb5b2: '아뇨', 0xb5b8: ', 리히터가', 0xb5c6: '미쳐 버린 원인을', 0xb5dc: '알아낼 때까진...', 0xb601: '그렇군...', 0xb613: '그럼 ', 0xb620: '가는', 0xb62a: '길에 신의 가호가', 0xb641: '있기를. ', 0xb64c: '잘 가라.', 0xb668: '당신도요, 알카드.', 0xb681: '안녕히.', 0xb6ad: '무사했나 보군.', 0xb6cf: '알카드!', 0xb6dc: '무사해서 정말', 0xb6ec: '기뻐요!', 0xb709: '미안하다.', 0xb718: '내 탓에 당신이', 0xb72d: '친아버지와', 0xb740: '싸워야만 했다...', 0xb75f: '걱정 마라.', 0xb76d: ' 나도', 0xb778: '그를 쓰러뜨릴', 0xb78a: '이유가 있었다.', 0xb7a6: '그래도 당신에겐', 0xb7ba: '괴로웠겠지.', 0xb7d7: '그렇다. ', 0xb7e1: '하지만', 0xb7f0: '늘 기억해 둬라. ', 0xb802: ' ', 0xb809: '악이 승리하는', 0xb81c: '데 필요한 것은', 0xb831: '선한 자들의', 0xb840: ' ', 0xb849: '침묵뿐이다...', 0xb85a: ' ', 0xb871: '명심하지.', 0xb891: '알카드, ', 0xb89e: '이제', 0xb8aa: '뭘 할 거죠?', 0xb8c2: '내 핏줄에 흐르는', 0xb8d9: '이 피는', 0xb8ea: '저주받', 0xb8f6: '았다. ', 0xb903: '이 세상을 위해서는', 0xb91b: '내가 영원히', 0xb92a: '사라지는 게 낫다.', 0xb955: '그래요...', 0xb96a: '잘 있어라. ', 0xb97d: '다시', 0xb985: '만날 일은 없다.', 0xb9b1: '알카드...', 0xb9ce: '그를 ', 0xb9dc: '쫓아가지', 0xb9e9: '않을 거야, ', 0xb9f8: '마리아', 0xba26: '미안해...', 0xba37: '그를 내 삶에서', 0xba4b: '떠나보낼 ', 0xba57: '수는', 0xba62: '없어.', 0xba74: '괜찮아.', 0xba86: '그를 쫓아가.', 0xba96: '어쩌면 그의 괴로운', 0xbaad: '영혼을 구할 거야.', 0xbacb: '고마워, 리히터...', 0xbae2: '잘 지내.', 0xbafe: '너도 잘 지내,', 0xbb0e: '아가씨.', 0xbb36: '아니', 0xbb3e: ', 이대로가', 0xbb4f: '좋아.', 0xbb56: ' 그의 고통을', 0xbb65: '덜 수 없어. ', 0xbb74: '언젠가', 0xbb7e: '우리 ', 0xbb88: '다시 ', 0xbb92: '만날', 0xbb99: '거야. ', 0xbba4: '그리고', 0xbbb2: '그땐', 0xbbb8: ' 아마...', 0xbbcd: '그렇군..', 0xbbe4: '가자. ', 0xbbf2: '모두가', 0xbbff: '기다리고 있어.', 0xbc1b: '그래,', 0xbc24: ' 어서', 0xbc2c: ' ', 0xbc32: '여길 나가자.',
}
SEL_RANGE = (0xb32e, 0xbc40)

MAR_KO = {
    0x1444: '인간 같긴 한데', 0x1455: '뭔가...', 0x1464: '여긴 무슨 일이죠?', 0x1494: '이 성을', 0x14a3: '파괴하러 왔다.', 0x14c6: '그럼 우리 목적은', 0x14d9: '같네요.', 0x14eb: '당분간은 믿을게요.', 0x1502: '저는 ', 0x150d: '마리아예요', 0x151e: '당신은요?', 0x1543: '알카드다', 0x155a: '말수가 적은', 0x156e: '타입이네요.', 0x1582: '뭐, ', 0x158c: '또 만나게', 0x159c: '되겠죠, ', 0x15a9: '당신이', 0x15b2: '살아 있다면.', 0x15c6: '안녕히.',
}
MAR_RANGE = (0x1424, 0x15d4)
DAI_CS = {0x3bf2: '나…'}

ARGOPS = (0x02, 0x03, 0x11)


def cs_runs(d, lo, hi):
    """Printable runs of a PS1 cutscene script; a leading wait/speed argument byte is not part of the run."""
    out = []
    for m in re.finditer(rb'[\x20-\x7e]+', d[lo:hi]):
        a, b = lo + m.start(), lo + m.end()
        if d[a - 1] >= 0x20 or d[b] >= 0x20:
            continue
        if d[a - 2:a] == b'\x0b\x09' or d[a - 3:a - 1] == b'\x0b\x09':
            continue
        if d[a - 1] in (0x02, 0x03, 0x11) and d[a - 2] not in ARGOPS:
            a += 1
        if a < b and re.search('[A-Za-z]', d[a:b].decode()):
            out.append((a, d[a:b].decode()))
    return out


def cs_items(d, ko, lo, hi):
    items = []
    for a, s in cs_runs(d, lo, hi):
        if a not in ko:
            continue
        nxt = d[a + len(s)]
        items.append(dict(off=a, en=s, cap=len(s), path='cutscene', newline_after=nxt == 0x01, ko=ko[a]))
    missing = set(ko) - {it['off'] for it in items}
    assert not missing, [hex(m) for m in missing]
    return items


# ---------------------------------------------------------------- builders
def api_item(x, off, end, ko, nl='\x01', limit=None, note=None):
    it = dict(off=off, en=dec2(x[off:end], ord(nl)), cap=end - off, path='api', nl=nl, ko=ko,
              orig=x[off:end].hex())
    if limit: it['limit'] = limit
    if note: it['note'] = note
    return it


def menu8_en(b):
    return ''.join(' ' if c == 0 else chr(c + 0x20) for c in b)


def menu8_items(x):
    W = words(x)
    tg = {}
    for i, w in enumerate(W):
        o = w - B
        if 0x2d4f0 <= o < 0x2dd00:
            tg.setdefault(o, []).append(i * 4)
    targets = set(tg)
    import draa
    items = []
    for off, ko in sorted(LIB_MENU8.items()):
        assert off in targets, hex(off)
        e = x.index(b'\xff', off)
        end = e + 1
        while end < len(x) and x[end] == 0 and (end == e + 1 or end % 4):
            end += 1
        assert x[e + 1] == 0, hex(off)
        assert not any(off < t < end for t in targets), hex(off)
        en = menu8_en(x[off:e])
        it = dict(off=off, en=en, cap=end - off, path='menu8', orig=x[off:end].hex())
        if ko is not None:
            try:
                b = draa.encode_a(ko) + b'\xff\x00'
            except ValueError:
                b = None
            if b is None:
                it['note'] = 'Korean %r not encodable; upper-case English used' % ko
                ko = None
            elif len(b) > it['cap']:
                it['note'] = 'Korean does not fit in place: relocated by libfix.py (upper-case English here)'
                it['want'] = ko
                ko = None
        if ko is None:
            ko = en.upper()
            it.setdefault('note', 'upper-case English (lower-case cells are Hangul jamo in the Korean sheet)')
        it['ko'] = ko
        items.append(it)
    return items


def lib_sheet():
    x = rd('ST/LIB/LIB.BIN')
    items = []
    for o in msgboxes(x):
        txt = dec2(x[o + 2:x.index(b'\0', o + 2)])
        items.append(api_item(x, o + 2, x.index(b'\0', o + 2), MSG_KO[txt], limit=x[o]))
    o = LIB_DESC_RANGE[0]
    while o < LIB_DESC_RANGE[1]:
        if x[o] == 0:
            o += 1; continue
        e = x.index(b'\0', o)
        items.append(api_item(x, o, e, LIB_DESC[o], nl='@', limit=210))
        o = e + 1
    for o, ko in LIB_SHOP.items():
        items.append(api_item(x, o, x.index(b'\0', o), ko, limit=240))
    for o, ko in LIB_ASCII8.items():
        e = x.index(b'\0', o)
        items.append(dict(off=o, en=x[o:e].decode(), cap=e - o, path='ascii8', ko=ko, orig=x[o:e].hex(),
                          note='raw-ASCII cell routine 0x801B191C: upper case here; libfix.py replaces the routine '
                               'with a Korean bitmap blit (ko)'))
    items += menu8_items(x)
    # 'Def HP' at 0x2da44 is also referenced at +4 ('HP'): only the word 'Def' -> upper case, no terminator
    items.append(dict(off=0x2da44, en='Def', cap=3, path='menu8', noterm=True, ko='DEF', orig=x[0x2da44:0x2da47].hex(),
                      note='suffix HP shared with another label; upper case only'))
    for o in obtained(x):
        items.append(api_item(x, o, o + 9, OBTAINED_KO, note='relic orb prefix + relic name'))
    assert len([i for i in items if i['path'] == 'api' and i.get('nl') == '@']) == len(LIB_DESC)
    return dict(file='ST/LIB/LIB.BIN', items=sorted(items, key=lambda i: i['off']))


def overlay_files():
    out = []
    for f in sorted(glob.glob(os.path.join(U, '**', '*.BIN'), recursive=True)):
        rel = os.path.relpath(f, U).replace(os.sep, '/')
        if rel == 'DRA.BIN' or os.path.basename(f).startswith('F_'):
            continue
        out.append(rel)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sheets = {}
    for rel in overlay_files():
        name = rel.split('/')[-1].split('.')[0]
        if name == 'LIB':
            continue
        x = rd(rel)
        items = []
        for o in msgboxes(x):
            e = x.index(b'\0', o + 2)
            txt = dec2(x[o + 2:e])
            if txt in MSG_KO:
                items.append(api_item(x, o + 2, e, MSG_KO[txt], limit=x[o]))
        for o in obtained(x):
            items.append(api_item(x, o, o + 9, OBTAINED_KO, note='relic orb prefix + relic name'))
        if items:
            sheets[name] = dict(file=rel, items=items)
    sheets['LIB'] = lib_sheet()
    x = rd('ST/SEL/SEL.BIN')
    sheets['SEL'] = dict(file='ST/SEL/SEL.BIN', script_start=SEL_RANGE[0] - 0x30,
                         note='ending dialogue: cutscene engine variant 0x801C0418 (not hooked yet)',
                         items=cs_items(x, SEL_KO, *SEL_RANGE))
    x = rd('BOSS/MAR/MAR.BIN')
    sheets['MAR'] = dict(file='BOSS/MAR/MAR.BIN', script_start=0x1424,
                         note='Maria: cutscene engine variant 0x8018C6A8 (not hooked yet)',
                         items=sheets.get('MAR', {}).get('items', []) + cs_items(x, MAR_KO, *MAR_RANGE))
    x = rd('ST/DAI/DAI.BIN')
    sheets['DAI']['script_start'] = 0x3a94
    sheets['DAI']['items'] += cs_items(x, DAI_CS, 0x3bf0, 0x3bf8)
    for name, sh in sorted(sheets.items()):
        sh['items'].sort(key=lambda i: i['off'])
        fn = os.path.join(TR, 'extra_' + name + '.json')
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(sh, f, ensure_ascii=False, indent=1)
        print('%-8s %-20s %s' % (name, sh['file'], ' '.join('%s:%d' % (p, sum(1 for i in sh['items'] if i['path'] == p))
                                                          for p in ('cutscene', 'api', 'menu8', 'ascii8'))))


if __name__ == '__main__':
    main()
