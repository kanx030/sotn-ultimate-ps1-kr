# English text drawn as graphics: what gfx.py changes

**Module:** `E:\SOTNKR\tools\gfx.py`
- Entry point: `patch_file(path, data) -> bytes`.
- `GFX_FILES` = F_GAME, F_GAME2, F_TITLE0, F_TITLE1, ST/SEL/F_SEL, ST/SEL/SEL, DRA.
- Every edit first checks that the target bytes are still the US originals. If they are not, it skips the edit and records "SKIPPED" in `gfx.LOG`.
- Running it twice changes nothing more.
- Output sizes are unchanged.
- draa's 8x8 sheet (F_GAME/F_GAME2 0x30000–0x31FFF) is never touched. I checked this after running `draa.patch_fgame` first.
- DRA was also checked after `build.patch_dra`: the compressed picture is still intact there, so the gfx patch applies.

**Previews:** `python tools\gfx.py` writes before/after PNGs to `E:\SOTNKR\work\gfx_preview\` (US on the left, patched on the right). They are grayscale, using index×17, except the logos, which use their real CLUT.
- `gfx_preview\raw\` holds the analysis dumps (U vs K block comparisons).

**Fonts:** all OFL.
- Galmuri 7/9/11 (`work\dl\galmuri`)
- Noto Sans KR and Noto Serif KR (Windows Fonts)

## File layout (needed to read the offsets)
- **F_\*.BIN graphics files:** a series of 64hw×256 VRAM columns. Each column is stored as four 0x2000-byte 32hw×128 4bpp blocks, in the order TL, TR, BL, BR.
  - Block n goes to VRAM x = base + (n//4)*64 + (n%2)*32, y = 256 + ((n//2)%2)*128.
  - I confirmed this against a VRAM dump from the save states. F_GAME 0x30000 lands at (896,256) as expected.
- **Compressed gfx:** DRA's `DecompressData` is at 0x800E8FAC. The format is an 8-byte dictionary followed by a nibble stream.
  - The read nibble is the high nibble first. The write nibble is the low nibble first.
  - Ops:
    - 0: zero×(n+19)
    - 1: 1 literal
    - 2: c×2
    - 3: 2 literals
    - 4: 3 literals
    - 5: c×(n+3)
    - 6: zero×(n+3)
    - 7–14: dictionary entry (0x1c = c, 0x2c = c c, 0x6n = zero×(n+3))
    - 15: end
  - `gfx.decompress` reproduces the uploaded VRAM exactly. `gfx.compress` is an optimal-parse encoder whose output is verified by decompressing it again.
- **Gfx bank entry:** `{u32 x<<16|y, u32 w<<16|h, ptr}`. Kind 4 means compressed. The loader is at 0x800E9228.

## Graphics changed

| File | Offset / location | Format | English | What was done |
|---|---|---|---|---|
| F_GAME.BIN, F_GAME2.BIN | 0x2C000–0x2FFFF and CLUT 0x41A00–0x41BFF (palettes 208–223) | 128×128 8bpp + 256-colour CLUT | "Castlevania – Symphony of the Night" logo on the Now Loading screen | **Rendered fresh from the title logo** (`gfx.fgame_logo`; v2, replaces the 1:1 port of K's blurry small logo + Galmuri7). Drawn by DRA 0x800E5120–0x800E519C as one sprite: tpage 0x9D, CLUT 0x1D0, uv (0,128)–(127,191) at screen (112,160)–(239,223), 1:1, so only cols 0–126 × rows 0–62 show (US ink cols 4–122 rows 0–62; K's copy reached col 127, clipped). The loading screen is 256 px wide and the title 512, so the faithful shrink is sx = 123/473, sy = 2·sx (US/K small logos match this). Title ink (patched F_TITLE0: K art + our Ultimate) → main title + X + swoosh Lanczos-shrunk (premultiplied alpha) to 123×38; "월하의 야상곡" cut out and shrunk at 1.5× that size (else 6 texels per syllable), right edge kept under the swoosh; light unsharp mask; "얼티메이트" redrawn pixel-sharp at this size (Noto Sans KR Black 12 px, unsmoothed FreeType, same Saturn gradient + 1 px dark-brown outline; scaling the title's 18 px version gave 5–7 texels per syllable and 메 read as 데) at rows 46–58, x 68–124. Composited on black (loading-screen background), alpha < 96/255 → index 0; new 255-colour CLUT (median cut + k-means in 15-bit RGB, index 0 = 0x0000 transparent, no other entry 0x0000, no STP bits as in US). Ink rows 0–58, cols 2–124. Same bytes in F_GAME and F_GAME2. Asserts the US logo + CLUT bytes. Preview `f_game_logo_v2.png` (US | previous | new, ×3 nearest; bottom row at display aspect). |
| F_GAME.BIN, F_GAME2.BIN | block 0x10000, rows 75–126 | 4bpp, box colour 2, glyph 4/5 | Pop-up words, mapped as below. | **Drawn** (Galmuri7, 7 px), each inside the original word's box. Stat names are right-aligned and 업/다운 left-aligned, so "힘 업" etc. join up as in the English. The 1 px top/bottom box border is lost (boxes are only 7 rows tall). |
| F_GAME.BIN, F_GAME2.BIN | block 0x16000, rows 104–127 | 4bpp, outline 1, ramp 2–F | "Now Loading" | **Drawn** "로딩 중" (Noto Sans KR ExtraBold, sheared to look italic, AA ramp, dark outline). |
| F_GAME.BIN, F_GAME2.BIN | block 0x38000, rows 50–60, x 48–95 | 4bpp, letters 1 outlined with 9 | "DEAD" "STONE" (HUD) | **Drawn** "사망" "석화" (Galmuri9 bold) in the same two halves. |
| F_GAME.BIN, F_GAME2.BIN | block 0x38000, rows 116–123 | 4bpp toggle pills | "ON/OFF" (two states) | **Drawn** "켬/끔" in the same colours (Galmuri7). Where these are used is not confirmed. |
| F_GAME2.BIN | block 0x18000, rows 44–83 | 4bpp, bg 9, text F | Richter HUD: "RICHTER REST ×00", "PAUSE PUSH START" | **Drawn** "리히터 ×00" (REST removed; the ×00 is untouched) and "일시정지". |
| F_TITLE0.BIN | logo blocks 0x20000, 0x22000, 0x28000, 0x2A000, 0x30000, 0x32000, 0x38000, 0x3A000; CLUT rows 112–114 of blocks 0x4000/6000/C000/E000/14000/16000/1C000/1E000 | 512×128 8bpp + three 256-colour CLUTs (normal / dark / fade) | Title-screen "Castlevania" logo | **Ported from K 1:1.** The K logo plus its CLUT rows were checked by rendering with the CLUT. Outside rows 112–114 the background blocks are identical in U and K. **Plus "얼티메이트"** (Saturn style, see F_GAME row): Noto Sans KR Black 18 px, gradient fill AA-blended into a 2 px dark outline, rows 74–94, x ≈ 375–472, right under the X swoosh (K ink ends at row 73; US ink covered rows 2–122, x 25–482, so this area is inside what the US title code draws). Each pixel uses the nearest existing colour of CLUT row 112 (index 0 / black excluded), so the dark/fade CLUT rows 113/114 fade it like the rest. `_ultimate_onto` asserts the area is empty. Preview `f_title0_logo.png` (real colours). |
| F_TITLE1.BIN | block 0x6000, rows 52–60 / 68–76 / 84–92 (x 0–31) | 4bpp. A 279 px line is stored as three 128 px pieces; colours 2/3/4 from top to bottom, shadow 1 | "PRESS START BUTTON" | **Drawn** "스타트 버튼을 누르세요" (Galmuri9 bold) on the same line and centre, then cut into the same pieces. The copyright text ("©1997 KONAMI … KCET", rows 16–46) is **kept**. |
| F_TITLE1.BIN | blocks 0x20000+0x22000 (256 px wide), rows 1–31 and 31–47 | 4bpp coverage 0–F | Prologue caption "JOURNEY BACK TO 1792 / and the Transylvanian countryside of Romania." + JP "「1792年 トランシルバニア地方」" | **Drawn** "1792년으로 거슬러 올라가 / 루마니아의 트란실바니아 지방." (Noto Serif KR, AA). Line 3 is **ported from K** ("「1792년 트란실바니아 지방」"). |
| ST/SEL/F_SEL.BIN | blocks 0x4000 (rows 0/32/64/96) and 0x6000 (row 16), plus the identical copy at 0x24000/0x26000 | 4bpp gothic headers: a 32×32 illuminated capital box and a text line | File copy / File delete / Name entry / Name change / File select | **Drawn.** The Latin capital is removed (box texture kept) and the first syllable is drawn there in Noto Serif KR Black. Only the Latin lower-case letters are removed; the gold key, fleurons, '&' and flourish are kept pixel for pixel. The Korean goes into the gaps the English lower case used (Galmuri11 bold, ramp 3/4/5 in a colour-1 outline; one size and one text row per header; under the Name headers' lower key ornament the glyphs sit on rows 21-31 without the bottom outline row; Galmuri9 only as fallback (Player select)): [파]일 & 복사, [파]일 & 삭제, [이]름 · 입력, [이]름 · 변경, [파]일 & 선택. (`gfx._header_text`; it asserts the text fits without touching ornament.) |
| ST/SEL/F_SEL.BIN | block 0x6000 rows 111–125 x 0–79; rows 0–7 x 104–127 (same in the 0x26000 copy) | 4bpp | "Name :" "Place :", "TIME:" | **Drawn** "이름 :", "장소 :" (Galmuri9 bold) and "시간" (Galmuri7). The small "lv" and the digits are kept. |
| ST/SEL/F_SEL.BIN | 'CARD' plates: block 0x2000 / 0x22000 rows 9–13 x 78–97 (slot 1) and 0x2A000 x 46–65 (slot 2); 'Name' plate: block 0x0000 / 0x20000 rows 88–94 x 70–89 | 4bpp, letters 5 on gold 7 | "CARD", "Name" | **Drawn** "카드", "이름" (Galmuri7, colour 5, colour-1 drop shadow) after the Latin letters are painted back to plate gold. Done in `selui.patch_plates` (it runs after the page-0xD Hangul cells; asserts the plate area is US). The slot digit behind "CARD" is kept. Preview `f_sel_plates.png`. |
| ST/SEL/SEL.BIN | 0x275BC–0x27DBB (raw 32hw×32 → VRAM 960,96; added by Ultimate) | 4bpp header (same style as above) | "Sound mode" | **Drawn** "[사]운드 모드" (same placement rule; flourish fragments below row 21 that the English letters had cut are cleared). |
| DRA.BIN | va 0x800C217C (file 0x2217C). Bank entry at va 0x800A36E8 → VRAM (800,256), 128×128 | compressed 4bpp, outline 1, ramp 2–F | "Life max up / Heart max up / Level up / Got an item" | **Drawn** "최대 HP 증가 / 최대 하트 증가 / 레벨 업 / 아이템 획득" (Noto Serif KR, slanted). Each Korean line is drawn inside the English line's ink box. Recompressed to 1566 bytes, which fits the original slot (1585 bytes; the next stream starts 1588 bytes in). The leftover bytes are zeroed and the pointer is unchanged. Rendering falls back to fewer AA levels if a font change ever makes the stream too big. |

**Pop-up word mapping** (F_GAME block 0x10000):
- CRITICAL!! → 치명타!
- GUARD → 가드
- MISS!! → 미스!
- CURSE → 저주
- STONE → 석화
- POISON → 독
- -DOWN → 다운
- -UP → 업
- STRENGTH → 힘
- INTELLIGENCE → 지능
- LUCKY → 행운
- DEFENCE → 방어력
- OFFENCE → 공격력
- PROTECTION → 내성 획득
- FROM → :
- FIRE → 불꽃
- DARK → 어둠
- HOLY → 신성
- ICE → 빙 (the box is only 11 px wide)
- THUNDER → 번개
- PHYSICAL → 물리

## Still English or not handled (needs a decision or more work)

| Where | What | Why not done |
|---|---|---|
| F_PROLO0.BIN (blocks 0x4000–0x1E000) | Flying letters "C A S T L E V A N I A" (big serif) in the prologue | Stylised title letters. K has "D R A C U L A X", which is also Latin. A Korean version would need the letter-sprite count and layout changed in the prologue code. Left as is. |
| F_GO.BIN | Gothic "GAME OVER" style letters (8bpp) | K is identical to US (also English), and changing the letter count needs code. Left as is. (The quote under it is part of the 256x256 8bpp background at 0x8000 and is now Korean: `engfix.py`, 11-11.) |
| F_TITLE1.BIN 0x6000 rows 16–46 | "©1997 KONAMI ALL RIGHTS RESERVED. DEVELOPMENT BY KCET." | Legal notice, kept on purpose. |
| F_GAME 0x38000 x≈100–127 | Small letters A C E G K L N R T (and "NRT") | Usage unknown (probably HUD or debug). Not changed. |
| F_GAME 0x14000 | JP "アイテム転送先" banner | JP leftover, unused in US. Not changed. |
| F_SEL name-entry alphabet | Gothic A–Z & ! - . ' ? | The player types a Latin name, so it is kept. |
| Item / relic pickup "Obtained" banner, enemy names | (strings, not graphics) | Not graphics: they use the 8x8 sheet / stage overlays (covered by draa/extraapply). |
| Area name cards | — | No stage-name graphics were found in the PS1 F_*/stage files. All stage F_ files are identical in U and K, except NP3/RNO3/RWRP/TE1–4, which hold no text. |
| Map screen (F_MAP.BIN) | — | Map bitmap only, no words. |

## Risks to check in the emulator
- **"얼티메이트" (F_TITLE0 rows 74–94 x 375–472):** placed only where the US logo had ink, so it should be inside the US sprites. Not confirmed from the title code; check it is not clipped.
- **Loading-screen logo (F_GAME/F_GAME2):** the sprite rectangle is confirmed from DRA (cols 0–126 × rows 0–62); the new logo stays inside it. Check it on real hardware/emulator (new CLUT colours, the bigger subtitle and Ultimate).
- **Title logo (F_TITLE0):** the K logo spans x 20–492; the US logo spans x 25–482. If the US sprites are cropped tightly rather than drawn as whole 128 px columns, about 5 px could be clipped at each end.
- **Status pop-up words:** the US sprite rectangles are assumed to cover each word's original box. The Korean text stays inside those boxes.
- **"Level up" picture:** each Korean line lies inside the English line's ink box, so it is safe unless the US sprites crop tighter than the English text itself.
- **ON/OFF pills, A C E G … letters and the Richter HUD:** where these are drawn has not been confirmed.

## SEL screens: fonts, strings and tiles (`tools/selui.py`)

`gfx.patch_file` calls `selui.patch(name, data)` for ST/SEL/SEL.BIN, BIN/F_TITLE1.BIN and ST/SEL/F_SEL.BIN, so the
build needs no change. BIN/SELRIC2.BIN (same layout outside its ending cutscene) is only patched if the build
calls `selui.patch('BIN/SELRIC2.BIN', data)` too. Every edit asserts the US bytes. Previews: `python tools/selui.py`
(also run by `python tools/gfx.py`): `sel_player_select_tiles.png`, `sel_small_strings.png`, `sel_gothic_strings.png`,
`f_title1_8x8_sheet.png`.

| What | How it is drawn in the game | Change |
|---|---|---|
| Button legends Select / Decide / Cancel / Input, "Not for-/matted", Yes / No / Confirm / Error; Ultimate's player-select screen: "Select a player", "Boss Richter", "Boss Maria", "Balance", "Dub", "Costume", "Version", "Saturn" | SEL 0x801BB9F8: 1 byte = 1 cell of the 8x8 sheet at VRAM (896,256), FF ends. On the title/SEL screens that sheet is F_TITLE1.BIN 0x30000 (a US copy; checked in the K-build save states: VRAM = F_TITLE1, not draa's K sheet) | 40 Hangul syllables drawn (Galmuri7, colour 6) into the kana cells 0x60–0x87 of F_TITLE1's copy; SEL never uses kana. Strings rewritten in place: 선택 / 결정 / 취소 / 입력, 포맷되지/않음, 예 / 아니오 / 확인 / 오류, 플레이어 선택, 보스 리히터, 보스 마리아, 밸런스, 음성, 의상, 버전, 새턴. PS1 / PSP / JP kept. |
| "Player select" header, ALUCARD / RICHTER / MARIA name plates | Built at run time from 8x8 tiles (0x801B3A48; bank 0x801AD518 = file 0x2D518, 232 tiles; lists 0x2F218 18×4, 0x2F308 / 0x2F32C / 0x2F350 11×3) and uploaded to VRAM (918,96…) | New images: [플]레이어 & 선택 (same header rule), 알카드 / 리히터 / 마리아 (Noto Serif KR Black, plate colours). Re-tiled into the 153 slots only these four lists use (117 needed); the portrait-frame list is untouched. |
| Gothic 16×16 words: "select your destiny", "new game", "used", "no data", "no / card" | US drawer 0x801BB8BC: a–z lookup (32 entries) in texture page 0xC (F_SEL's 2nd sheet copy). Name entry keeps using it. | The unused 12×16 drawer at 0x801BB7D0 (no callers) is replaced by a drawer that reads each byte as a 16×16 cell of page 0xD (VRAM 832,0 = F_SEL 0x28000–0x2FFFF): u=(b&15)·16, v=b&0xF0, 0 ends, 0xFF = blank (a NOP after the `lbu` covers the R3000 load-delay slot; without it the end byte was drawn as plate cell (0,0) and strings could be skipped). 23 syllables drawn into empty cells of that page (0x52–0x58, 0x62–0x68, 0xF0–0xFE; empty in F_SEL and in the VRAM dump). Strings: 그대의 / 운명을 / 선택하라, 새 게임, 사용 중, 데이터 없음, 카드 / 없음. The 6 call sites are redirected and the x positions re-centred (0x801B3400/18/30, 0x801B709C/B8, 0x801B7198). |

Still English on these screens (2026-11-07 check): the "Maria / Richter / Clear / Replay" file-box tags (plain ASCII strings at SEL 0x27EC0, drawn by 0x801BB504 — a text font, not a picture; not done), "PS1 / PSP / JP" option values (kept on purpose), the gothic name-entry alphabet (kept). Earlier note: the save-location names in the file boxes ("Black Marble / Gallery", "Outer Wall" … table at SEL 0x80180228, same small font: translatable the same way, ~60 more syllables fit in cells 0x88–0xDF); "Maria / Richter / Clear / Replay" file-box tags (SEL 0x27EC0, drawn by 0x801BB504, not examined); the gothic name-entry alphabet (kept on purpose).

Risks: the kana cells of the F_TITLE1 sheet become Hangul (only SEL draws with that sheet while it is in VRAM); the gothic drawer assumes VRAM page (832,0) rows 80–111 / 240–255 stay as F_SEL loads them (true in all SEL save states).
