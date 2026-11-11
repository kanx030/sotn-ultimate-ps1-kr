S0="찮누구냐炎려명계의나와라내종복아!央이피냄새….설마성을건진리를버俺틀림없어그자加는벨몬드가주고?대단하네필요도겠무순일런말찾닐데렇지히터,알있인解년실분여기거야시만界면한좋워로친절럼부탁할게"
S1="답않젠잠카해서조상프함께귤쓰러뜨린줌너던저에래뒤다응끝간과혈귀싸움은사획냥감금꾼쓸모제곳었군크수했안났백작님활눈앞렸역왜원놈영심것족힘름당신꿈속죽점음빈렴소갈오머니괜찮으두행맞미들막습살느람間"
S2="았깨천잡련때적왔유처관앙치길닌같론걸몸악꿰뚫氣록개貴보儀랑난뚝또체셨숨까직편십잘각셔急돈용결국위받랜번세코꺾롬란킬넘망존스멸케른헌운압暁연쪽탐욕날궤변념통솔되릴끌옳닫近엇씀삶향슬광뿐놓따"
import json as _j, os as _o
_used=_j.load(open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)),'used.json')))
TAB={int(c,16):ch for c,ch in zip(_used,S0+S1+S2)}
assert len(S0+S1+S2)==len(_used)
S3="더럽파였됐테줘랄럴맡흡양밤껍헤매목돼숨증죄낫박르져환볼엔줄못쩔생바괴선반울태혀떨몰낼탓숙흐띄택후회험담석녀쁘풀됩"
_u2=_j.load(open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)),'used2.json')))
assert len(_u2)==len(S3)
TAB.update({int(c,16):ch for c,ch in zip(_u2,S3)})
FW={0x8140:' ',0x8141:',',0x8142:'.',0x8148:'?',0x8149:'!',0x815b:'-',0x8160:'~',0x8163:'…',0x8164:'‥',0x8169:'(',0x816a:')'}
FIX={0x8a5c:'장',0x8a6c:'중',0x8ab0:'정',0x8ba0:'롭'}
TAB.update(FIX)
S4="열문힌방짓밟온텐1째켜뭐샤트식둘호뜻애믿넌뻔비돌청손떼물전달졌혼산능싶된잊우권삼맹패잃순참재육암흑예끼쉽앤쳐빌충든례꾸겁"
_u3=_j.load(open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)),'used3.json')))
assert len(_u3)==len(S4)
TAB.update({int(c,16):ch for c,ch in zip(_u3,S4)})
TAB.update({0x89da:'슨',0x8b65:'습',0x8a67:'큘',0x8beb:'떻'})
TAB.update({0x8a4d:'외',0x8a5d:'루',0x8b4b:'둠',0x8b4e:'녔',0x8b4f:'겉',0x8b83:'옛',0x8baf:'깊',0x8bb5:'크',0x8bb6:'윽',0x8bb8:'썩',0x8bba:'빠',0x8acb:'슴'})
