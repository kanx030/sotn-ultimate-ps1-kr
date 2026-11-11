"""Write a RetroArch cheat file (GameShark codes) for the test build: F1 → Cheats → Load Cheat File.
python make_cheats.py -> E:\\SOTNKR\\test\\cheats\\SOTN_KR_test.cht"""
import os
OUT = r'E:\SOTNKR\test\cheats\SOTN_KR_test.cht'
cheats = []
def add(desc, codes, on=False):
    cheats.append((desc, '+'.join(codes), on))
w16 = lambda a, v: '%08X %04X' % (0x80000000 | (a & 0xFFFFFF), v & 0xFFFF)
w8 = lambda a, v: '%08X %04X' % (0x30000000 | (a & 0xFFFFFF), v & 0xFF)
add('HP 무한 (9999)', [w16(0x97BB8, 9999), w16(0x97BB4, 9999)])
add('MP 무한', [w16(0x97BC8, 999), w16(0x97BC4, 999)])
add('하트 무한', [w16(0x97BC0, 999), w16(0x97BBC, 999)])
add('골드 999999', [w16(0x97C04, 0x423F), w16(0x97C06, 0x000F)])
add('렐릭 전부 획득', [w8(0x97964 + i, 1) for i in range(30)])
add('마법 전부 습득', [w8(0x97982 + i, 1) for i in range(8)])
add('손 아이템 전부 9개', [w8(0x9798A + i, 9) for i in range(1, 176)])
add('몸 장비 전부 1개', [w8(0x97A3A + i, 1) for i in range(1, 90)])
add('도서관 카드 9개', [w8(0x9798A + 166, 9)])
add('능력치 99 (힘/체력/지능/행운)', [w16(a, 99) for a in (0x97BCC, 0x97BD0, 0x97BD4, 0x97BD8)])
add('음성: 일본어', [w8(0x97BAF, 0x20)])
add('음성: PS1 영어', [w8(0x97BAF, 0x08)])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('cheats = %d\n\n' % len(cheats))
    for i, (d, c, on) in enumerate(cheats):
        f.write('cheat%d_desc = "%s"\ncheat%d_code = "%s"\ncheat%d_enable = "%s"\n\n' % (i, d, i, c, i, 'true' if on else 'false'))
print('wrote', OUT, len(cheats))
