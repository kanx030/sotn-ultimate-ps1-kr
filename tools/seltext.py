"""SEL (title / file select) menu messages -> Korean. (offset, original, korean, capacity bytes). NUL-terminated in place."""
import sys
from st0text import patch_runs, enc

D = b'\x81D'; Q = b'\x81H'
RUNS = [
    (0x3010c, b'Checking Memory Card' + D, '메모리 카드 확인 중．', 23),
    (0x30124, b'Do not remove Memory Card' + D, '메모리 카드를 빼지 마세요．', 27),
    (0x30140, b'You won\x81ft be able to save', '게임을 저장할 수 없게', 27),
    (0x3015c, b'your game' + D + b' Is that OK' + Q, '됩니다． 괜찮습니까？', 27),
    (0x30178, b'Select file to be loaded' + D, '불러올 데이터를 선택하세요．', 31),
    (0x30198, b'Press Start button', '스타트 버튼을 눌러', 19),
    (0x301ac, b'to begin new game' + D, '새로 시작하세요．', 19),
    (0x301c0, b'Select New Game', '새 게임을 골라', 15),
    (0x301d0, b'to start from beginning' + D, '처음부터 시작합니다．', 27),
    (0x301ec, b'Input \x81h\x81hRICHTER\x81h\x81h to play', '이름에 ””RICHTER””를', 31),
    (0x3020c, b'as Richter Belmont' + D, '넣으면 리히터 플레이．', 23),
    (0x30224, b'No data found', '이 카드에는', 15),
    (0x30234, b'on this Memory Card' + D, '데이터가 없습니다．', 23),
    (0x3024c, b'Select the file', '이름을 바꿀', 15),
    (0x3025c, b'you wish to rename' + D, '파일을 고르세요．', 23),
    (0x30274, b'Changing Name' + D, '이름 변경 중．', 15),
    (0x30284, b'Name changed' + D, '변경 완료．', 15),
    (0x30294, b'Loading error' + D, '불러오기 오류．', 15),
    (0x302a4, b'Save error' + D, '저장 오류．', 15),
    (0x302b4, b'Select file', '파일을 골라', 11),
    (0x302c0, b'to be copied' + D, '복사하세요．', 15),
    (0x302d0, b'Where do you want', '어디에', 19),
    (0x302e4, b'to copy to' + Q, '복사할까요？', 15),
    (0x302f4, b'OK to overwrite data' + Q, '기록을 덮어쓸까요？', 23),
    (0x3030c, b'Copying data' + D, '복사 중．', 15),
    (0x3031c, b'File copied' + D, '복사했습니다．', 15),
    (0x30344, b'to be erased' + D, '삭제하세요．', 15),
    (0x30354, b'Is it OK to erase file' + Q, '삭제해도 괜찮습니까？', 27),
    (0x30370, b'File erased' + D, '삭제했습니다．', 15),
    (0x30380, b'Delete error' + D, '삭제 오류．', 15),
    (0x30390, b'Loading Memory Card' + D, '메모리 카드 읽는 중．', 23),
    (0x303a8, b'Version error' + D, '버전 오류．', 15),
    (0x303b8, b'Format Memory Card', '카드를 포맷할까요？', 19),
    (0x303cc, b'in slot \x82P' + Q, '카드슬롯１번', 15),   # slot digit must stay at byte offset 8
    (0x303dc, b'Formatting completed' + D, '포맷 완료．', 23),
    (0x303f4, b'Formatting error' + D, '포맷 오류．', 19),
]

def patch(sel):
    return patch_runs(sel, RUNS, terminate=True)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    bad = []
    for off, en, ko, cap in RUNS:
        try:
            b = enc(ko); print('%x %2d/%2d %s %s' % (off, len(b), cap, 'OK ' if len(b) <= cap else 'BAD', ko))
            if off == 0x303cc: assert b[8:10] == b'\x82P', b
        except KeyError as e:
            bad.append(str(e)); print('%x MISSING %s %s' % (off, e, ko))
    print('missing', bad)
