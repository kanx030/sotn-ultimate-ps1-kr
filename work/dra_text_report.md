# DRA.BIN text report: US "SOTN Ultimate" vs the Korean (JP-based) build

How to read the addresses:
- **va**: RAM address. DRA file offset = va − 0x800A0000.
- **U** means `E:\SOTNKR\work\U\DRA.BIN`. **K** means `E:\SOTNKR\work\K\DRA.BIN`.
- Helper scripts are in `C:\Users\ADMINI~1\AppData\Local\Temp\claude\7526c322010bebb4\0bbab42c-1558-43dc-97c9-4491df8ea710\scratchpad\dra\`. `common.py` has the reference finder, caller finder and decoders.
- PNG dumps in the same folder: `fg2_diff.png` shows the U and K menu font sheets and logo; `kname.png` shows K item names rendered.

---

## 0. The three text engines in US DRA

| # | Engine | Entry (va) | Glyph source | Cell / advance | String format |
|---|---|---|---|---|---|
| A | **8x8 menu font**: `MenuDrawStr` 0x800F4494 → `MenuDrawChar` 0x800F4434 → `MenuDrawSprite` 0x800F356C | 0x800F4494 (str, x, y, ctx) | VRAM sheet at (896,256), tpage 0x1E, CLUT 0x196. Source: **`BIN/F_GAME.BIN` offset 0x30000–0x31FFF** (one 128x128 4bpp block; F_GAME is stored column-major in 32hw×128 blocks). `F_GAME2.BIN` probably has its own copy. | 8x8 cells, u=(c&15)*8, v=(c&0xF0)>>1; 8 px advance | 1 byte per char; US encoding is ASCII−0x20 (0x00 = space). **0xFF xx** = overlay `xx` on the previous cell at (x−8, **y−8**). **0xFF 0x00** = end. Bytes `C0 D2` after a char switch a flag at 0x8013784C (used in spell combo strings). Arrow icons are 0xE0–0xE7. |
| B | **Glyph-API "draw string into VRAM"**: `DrawTextToVram` 0x800F7800 (str, mode, narrow). Clear: 0x800F7650. Wrapper: 0x800F7B88. | 0x800F7800 | **0x80104EDC** (the glyph API; its jal Krom2RawAdd at 0x80104EF8 is already redirected to `LOOKUP_RAM` by build.py). It shrinks the 16x15 1bpp glyph to 12x16 4bpp, 6 bytes per row, into the buffer 0x80137EF8. | Proportional: each glyph is trimmed to its used columns, then LoadTPage (0x8001112C) into the text area at VRAM x=384 (tpage 6) / 448 (tpage 7). The row comes from 0x800F30F4(mode): row = (mode&0x7F)*16, and 0x80 adds 3 rows. Mode bit 0x100 selects the +64hw page. | NUL-terminated. `a`–`z` → 0x8281+, `A`–`Z` → 0x8260+, space → 0x8140 plus a 2-byte gap. **Every other byte is read as the high byte of a 2-byte SJIS-style code**, so digits and punctuation must be full-width (0x824F…, 0x8144 "．", 0x8148 "？", 0x8169/816A "（）", 0x8166 "'", 0x817C "－"). 0x8168 skips 2 extra bytes. ⇒ **Korean 2-byte codes (≥0x8140) work today with no code change.** |
| C | **Pre-rendered 12x16 label cells**: set renderer 0x800F76F4 (str2, mode); label drawer 0x800F4364 (idx_str, x, y, ctx, arg5) | 0x800F4364 | 0x800F76F4 sends a 2-byte string through the glyph API into one row of 12x16 cells at fixed 3hw (12 px) steps. 0x800F4364 then draws sprites from cell indices: u=(c&15)*12, v=(c>>5)*16, tpage 6+((c&0x10)?1:0), CLUT 0x1A1. | 12x16, 12 px advance | Index string; 0xFF = end. |

The 16x15 glyph API is called from DRA only at 0x800F7748 (inside 0x800F76F4, engine C) and 0x800F7934 (inside 0x800F7800, engine B). Engine A never reaches it.

---

## 1. Categories (US)

### 1.1 Equipment (hand items: weapons, shields, consumables), engine A for names, B for descriptions
- **Table:** `g_EquipDefs` va **0x800A499C**, stride **0x34**, 228 entries (176 used; unused entries point to 0x800DC804 = "\xFF").
  - +0x00: name ptr
  - +0x04: description ptr
  - +0x2C / +0x2E: icon / palette
- **Names:** US 1-byte encoding, 0xFF-terminated, longest 14 chars, 1924 bytes total. Pool is about 0x800DE400–0x800DF230.
  - Inventory grid: function 0x800F6688 → `GetEquipName` 0x800FB5EC → MenuDrawStr at 0x800F68C4. Two columns at x = 40 + col*168, rows y = 4 + row*12. The count is drawn at x+128, so **names can be at most 128 px wide (16 cells) and must fit a 12 px row pitch**.
  - Equipped-slot panel: 0x800F6C50 (0x800F7140 / 71B0 / 723C / 72B8). x=0x70, row pitch 12 or 13.
- **Descriptions:** ASCII plus SJIS punctuation, NUL-terminated, longest 35 bytes, through engine B.
  - Callers: 0x800F8BE0 → 0x800F8B54 → 0x800F7800 (mode 2, wide = 0x90 bytes = **288 px**). Also 0x800FB018 → 0x800F8D3C.
  - With 12 px Korean glyphs that is about 22–24 syllables per line.

### 1.2 Accessories (head, body, cloak, other)
- **Table:** va **0x800A77EC**, stride **0x20**, 93 entries.
  - +0: name, +4: description, +0x18 / +0x1A: icon / palette.
  - The first entry of each category is "----" / "Unequip".
- Names and descriptions use the same paths and limits as 1.1 (name refs at 0x800F71F0 and 0x800FB5FC; description at 0x800F8CDC).

### 1.3 Relics, engine B for both names and descriptions
- **Table:** va **0x800DFC28**, stride **0x10**, 31 used.
  - +0: name (ASCII; some have a leading space), +4: description (ASCII + SJIS), +8: flags.
- The relic list is pre-rendered by **0x800F7C18**:
  - It strcpy's (0x800160A4) each name to the stack, then calls 0x800F7800 with narrow = 1, so names get 0x3C bytes = **120 px**.
  - Modes are 0x80+n / 0x103+n (rows ≥3, both pages).
  - Descriptions are drawn at 0x800FA7B0 and 0x800FAA28 (mode 2, 288 px).
- The relic *pickup* banner ("Obtained ...") is drawn by stage overlays (EntityRelicOrb), not DRA.

### 1.4 Spells (Alucard's special moves), engine B for names and descriptions, A for button combos
- **Table:** va **0x800DF780**, stride **0x1C**, 8 used.
  - +0: name (ASCII), +4: combo (0xE0–0xE7 arrow cells, `C0 D2`, 0xFF end), +8: description (ASCII).
- Names are pre-rendered by 0x800F7D50 (call at 0x800F7E10).
- The list is drawn by 0x800F5870. It uses MenuDrawStr for the combo and the "Special Moves List" header.
- Descriptions are drawn at 0x800FAB38 and 0x800FABB4 (engine B).
- **Caution:** 0x800FAD1C sends the *description* to the 2-byte-only renderer 0x800F76F4 (mode 2). This looks like a JP leftover. If it is ever reached, ASCII text would become garbage there, while Korean 2-byte text would render correctly.

### 1.5 Menu labels, `g_MenuStr` pointer table va **0x800A838C** (110 entries, engine A)
US 1-byte strings in the pool 0x800DF238–0x800DF774. Index, text, and the drawing function:

| Index | Text | Drawn by |
|---|---|---|
| 0 | ALUCARD | status screen 0x800F519C; familiars 0x800F5C74 |
| 1–4 | STR CON INT LCK | 0x800F519C / 0x800F4FA4 |
| 5–8 | EXP NEXT GOLD LEVEL | |
| 9–11 | TIME ROOMS KILLS | |
| 12–15 | HP MP HEART STATUS | |
| 16–19 | Button settings, Cloak lining, Cloak color, "eeeee" (colour-bar cells) | system menu 0x800F606C; cloak 0x800F4718 |
| 20–21 | Exterior, Lining | |
| 22–29 | Right hand, Left hand, Jump, Special, Wolf, Mist, Bat, (JP katakana leftover) | button config 0x800F4C4C |
| 30–31 | Normal, Reverse | 0x800F4DC4 |
| 32–34 | Sound, Stereo, Mono | 0x800F4E50 |
| 35–36 | Window color, Time attack | |
| 37–40 | GOOD POISON STONE CURSE (status ailment) | 0x800F519C |
| 41 | "------------------------------" | time-attack list 0x800F4A70 |
| 42–44 | ALUCART, LEVEL, EXP | |
| 45–51 | familiar names: alucart, Bat, Ghost, Faerie, Demon, Sword, Sprite, N.Devil | 0x800F5C74 |
| 53–84 | time-attack events ("Richter defeats Dracula", "Defeat Olrox", … "First Maria meeting") | 0x800F4A70 |
| 85–91 | equip slot names: Right hand, Left hand, Head, Body, Cloak, Other (×2) | |
| 92–96 | main menu: Equip, Spells, Relics, System, Familiars | 0x800F6454 |
| 97–98 | Familiar List, Special Moves List | |
| 99–109 | equip categories: S.sword, Sword, Throw 1, Fist, Club, Two-hand, Food, Bomb, Throw 2, Shield, Medicine | 0x800F6550 |

Also on engine A: "Holder" at va 0x800DC064 (0x800F4CC8, 0x800F5768). Gold, level and other numbers are drawn by MenuDrawInt 0x800F459C (digit cells 0x10–0x19).

### 1.6 ATT / DEF on the status and equip screens, engine C
- va 0x800A2B30 → "ＡＴＤＥＦ" (0x800DC048). It is rendered once by 0x800F76F4 at 0x800F9DEC (mode 0 = row 0, page 0).
- Label strings:
  - 0x800A2B34 → `00 01 01 FF` = A T T
  - 0x800A2B38 → `02 03 04 FF` = D E F
- Drawn by 0x800F4364 at 0x800F55D0 and 0x800F56F0 (inside 0x800F519C).
- **This is the JP/K kanji-label mechanism; US kept only these 5 cells.**

### 1.7 System menu help and short messages, engine B
- Pointer table va **0x800A2B04**: "？？？？？", "Button set－up", "Select front／back of reversible cloak", "Custom cloak settings", "Window color settings", "Sound settings", "Time from game start". Drawn at 0x800FA34C (inside the big menu task 0x800F9B1C).
- "Assign the function to each button．" at va 0x800DC11C, drawn at 0x800FA57C → 0x800F7800.
- Blank full-width-space strings 0x800DC0D4 / 0x800DC0F4 clear the description line.

### 1.8 Memory card / save messages, engine B (via 0x800F7B88 → 0x800F7800 narrow, 120 px)
- Strings va 0x800DC694–0x800DC7DC: "Data saved．", "Memory Card", "  not found．", "is Defective．", "Memory Card is", "not formatted．", "Cannot", "overwrite file．", "No game", "data found．", "   ０ memory", "blocks available．", "  Memory card", "  format error．", "  Select the slot．", " Slot １/２", " Wish to format？", " Overwrite data？", "   Wish to save？", "Yes ", "  No  ".
- Drawn by the save/load dialog code at 0x80101B4C–0x801023A4 (21 calls). The dialog sprites come from 0x801016E4.
- Each string is passed as an immediate `lui/addiu` pair, not through a table. Relocating one means patching that pair.
- The PS1 memory-card *directory title* is built in SJIS from the tables at va 0x800A1D04 / 0x800A1D64 / 0x800A1DE4 (JP area-name kanji). The BIOS shows it, not the game. Leave it alone.

### 1.9 Enemy names
- `g_EnemyDefs` va **0x800A8544**, stride **0x28**, about 420 entries (186 named).
  - +0: name, US 1-byte encoding, 0xFF end, longest 15.
- DRA does not index this table itself except for the damage-calculation copy (0x800FD1A4). The Faerie-Scroll name display was **not found as a direct reference in DRA**; it probably goes through `g_api.enemyDefs` from the HUD or overlay side.
  - Next step: an emulator read-watch on `name ptr` (0x800A8544 + id*0x28).
- PS1 US has no bestiary.
- Whatever draws them must use engine A or a BlitChar-style 8x8 blitter, because the encoding is the 8x8 one.

### 1.10 Not text in DRA (graphics or overlays)
- **Graphics in F_GAME.BIN:**
  - "LEVEL UP", HP/MP/heart digits, damage numbers, "Now Loading", the HUD frame.
  - The Castlevania logo (blocks 0x2C000–0x2FFFF). **K replaced the logo with a Korean "악마성 드라큘라 X" logo at the same offsets.**
  - CLUT data at 0x40000–0x41FFF differs too (501 bytes).
  - A leftover JP banner "アイテム転送先" ("item transfer destination") is also there.
- **Stage-overlay text (out of scope here):** item pickup name pop-ups (they read `g_api.equipDefs` names and blit 8x8 chars), relic orb "Obtained" banner, shop/library menus (LIB), cutscenes. The cutscenes are already handled by build.py.

---

## 2. How the Korean (JP-based) K\DRA.BIN does the same things

The K engines are function-for-function the same as US:

| Engine | US | K |
|---|---|---|
| MenuDrawStr | 0x800F4494 | 0x800F6AD4 |
| MenuDrawChar | 0x800F4434 | 0x800F6A74 |
| 12x16 label drawer | 0x800F4364 | 0x800F69A4 |
| 2-byte set renderer | 0x800F76F4 | 0x800F9B28 |
| glyph API | 0x80104EDC | 0x801068B4 (Krom lookup → K exe 0x800107A0) |

| Category | K storage | K drawing |
|---|---|---|
| Equipment / accessory **names** | Pointers into **0x801FA5xx**, i.e. data copied together with the font (K exe offset 0x243E8 + (va − 0x801F0000)). Format: 8x8 cell codes with **0xFF xx overlays** (one syllable = base cell plus overlaid piece), "FF 00" end. | Engine A, unchanged code except **overlay offset y−2** (K 0x800F6B48 `addiu a2,a2,-2`; US 0x800F4544 has −8). The K menu sheet (`K\BIN\F_GAME.BIN` 0x30000) keeps 0–9, symbols and A–Z, and replaces lower case, kana and kanji with Hangul pieces (see `fg2_diff.png`; `kname.png` shows "맨손", "캡슐 몬스터1", "실드 로드", "레더 실드" …). Each syllable is **8 px wide**, so it fits the US 16-cell / 12-px-row layout. |
| Descriptions (equip/acc/relic/spell) | 2-byte Korean codes in the DRA pool (e.g. K equip table 0x800A4B70: name ptr, desc ptr 0x800DE8DE "장비 없음(맨손)"). | Glyph API (engine B). |
| Relic names | 2-byte Korean (K relic table at file 0x8728: "소울 오브 배트" …). | Engine B. |
| Big labels: ATT/DEF, main menu, equip categories, slot names, familiar / special-move list headers | Three 16-glyph 2-byte set strings: K ptrs 0x800A2D64/68/6C → " 갑검격곤공구권기단도람력른마망", "무방봉비사살손스시식약양어역오옷", "왼음일장타탄템토투패폭필설정…". They are rendered at K 0x800FBDA0–0x800FBDC4 with modes **0, 0x100, 1** (row 0 page 0, row 0 page 1, row 1 page 0). Index strings are at K 0x800A2D70–0x800A2DD8. | Engine C (0x800F69A4, 11 call sites in K vs 2 in US). |

The K index strings for engine C:

| K ptr | Indices | Text |
|---|---|---|
| 0x2D70 | 05 03 0C | 공격력 (ATT) |
| 0x2D74 | 11 1C 0C | 방어력 (DEF) |
| 0x2D78 | | 필살기일람 (Special Moves List) |
| 0x2D7C | | 장비 (Equip) |
| 0x2D80 | | 필살기 (Spells) |
| 0x2D84 | | 마도기 (Relics) |
| 0x2D88 | | 설정 (System) |
| 0x2D8C–0x2DB4 | | 단검 검 투검 권 곤봉 양손검 음식 폭탄 투사 방패 약 (equip categories) |
| 0x2DB8–0x2DD0 | | 오른손무기 왼손무기 투구 갑옷 망토 기타 (slot names) |
| 0x2DD4 / 0x2DD8 | | 사역마 (Familiars) / 사역마일람 (Familiar List) |

- K leaves GOOD/POISON/STONE/CURSE, STATUS and similar in **English** (8x8).
- K places its names inside the font RAM block. Our build uses that block for the K font plus the fontext glyphs (slots 1210+), so **do not reuse K's 0x801FA5xx pointers**. Copy the bytes into US DRA space instead.

---

## 3. Proposed approach per category

### Step 1: engine B categories (data only, easy)
**Covers:** equipment and accessory descriptions (1.1, 1.2), relic names and descriptions (1.3), spell names and descriptions (1.4), system help (1.7), button-assign text, memory-card / save messages (1.8).

1. Write the strings as NUL-terminated byte strings: Korean syllables as their 2-byte codes (`kmap.encode` / `fontext`). ASCII letters and space can stay. **Digits and punctuation must be full-width SJIS** (０–９ = 0x824F–0x8258, ．= 0x8144, ？= 0x8148, （）= 0x8169/0x816A, ・= 0x8145, －= 0x817C). A bare ASCII digit would swallow the next byte.
2. Redirect the pointers:

   | Strings | Pointer location |
   |---|---|
   | Equipment descriptions | entry+4 at 0x800A499C + i*0x34 |
   | Accessory descriptions | 0x800A77EC + i*0x20 + 4 |
   | Relic names / descriptions | 0x800DFC28 + i*0x10 (+0 / +4) |
   | Spell names / descriptions | 0x800DF780 + i*0x1C (+0 / +8) |
   | System help | 0x800A2B04–0x800A2B1C |
   | Button-assign text | the lui/addiu pair at 0x800FA574–0x800FA57C |
   | Memory-card / save messages | the lui/addiu pairs at 0x80101B40… (see 1.8) |

3. Width limits: about 288 px (≈22–24 syllables) for descriptions; about **120 px (≈9–10 syllables)** for relic names, spell names and save messages.
4. Space for the strings: the English pool 0x800DB990–0x800E0B80 (about 17 KB) is freed as each English string is replaced. Repack each pool in place. Korean is often shorter in bytes than English.
   - Zero-filled regions that stayed zero in all three RAM dumps: va 0x800B4EBE–0x800B607C (4.5 KB) and 0x800CDD20–0x800CF328 (5.6 KB). They are candidates, but could be transparent graphics. Verify before using them.
5. Optional quality step: 0x80104EDC squeezes 16 px glyphs to 12 px. Making it output 16 px (8 bytes per row) also needs the 5-byte column copy, the 6-byte stride, the 96-byte buffer and the 12x16 cell maths in 0x800F7800, 0x800F76F4 and 0x800F4364 changed. That is a medium-size job; leave it for later.

### Step 2: engine C big labels, copying K (easy–medium)
**Covers:** ATT/DEF, main menu, equip categories, slot names, familiar and special-move list headers.

1. Replace the set string 0x800A2B30 with K's three 16-glyph strings (or a custom set of up to 48 syllables; 256 cells are addressable).
2. At 0x800F9DE4 (`lui a0 / lw a0,0x2B30 / jal 0x800F76F4 / a1=0`), jump to a small stub in the font-ext area that calls 0x800F76F4 three times with modes 0, 0x100, 1, exactly like K 0x800FBDA0. Check first that US does not use text rows 1 and page-1 row 0 for something else: US engine B uses mode 2 and 0x80+/0x103+ rows, so they should be free.
3. Rewrite the index strings 0x800A2B34 / 0x800A2B38 (ATT/DEF) with K's 0x2D70 / 0x2D74 values (05 03 0C / 11 1C 0C).
4. For labels now drawn by MenuDrawStr, hook the entry of **MenuDrawStr 0x800F4494** instead of rewriting each call site:
   - If `str[0] == 0xFE`, store arg5 = 1 at sp+16 and branch to 0x800F4364 with str+1. The 12x16 drawer reads arg5 at `lw s4,88(sp)`, so build a 0x48-byte frame or shim.
   - Point g_MenuStr entries 85–109 and 92–98 at `FE <indices> FF` strings.
   - Labels become 12 px per syllable, as in K, which has these exact labels at the same screen positions.

### Step 3: engine A categories, the K-sheet route (medium–hard, mostly data)
**Covers:** equipment and accessory names, the remaining g_MenuStr labels (status words, button config, sound/cloak/window options, time-attack list, familiar names), enemy names.

1. Copy the K menu sheet `K\BIN\F_GAME.BIN[0x30000:0x32000]` over US `F_GAME.BIN` (and the matching block of `F_GAME2.BIN`, after checking which mode loads it). Also bring over K's CLUT changes at 0x40000+ if the sheet colours need them.
   - Lower-case ASCII cells are lost. Every visible engine A string must then be Korean or upper case. Digits, symbols, A–Z and the 0xE0–0xE7 arrows stay at the same positions.
2. Patch US **0x800F4544** `24c6fff8` → `24c6fffe`, so overlays sit at y−2 as in K.
3. Build an encoder for syllable → K cell sequence:
   - Label the K sheet cells (base cells plus overlay pieces) and verify against all K name strings. `kname.png` shows the renderer is already correct.
   - K's own names (K exe 0x243E8 + (ptr − 0x801F0000), "FF 00" terminated) can be reused directly for equipment and accessories. They are translations of the JP names, so map them by item index (the JP and US tables have the same order).
4. Repoint names in g_EquipDefs, the accessory table, g_MenuStr (0x800A838C) and g_EnemyDefs (0x800A8544).
   - Limits: 16 cells (16 syllables) in the inventory and 12-px rows.
   - Beware the `C0 D2` check at 0x800F44DC–0x800F4508. A Korean string containing the byte pair C0 D2 right after a char would trigger the flag. Avoid it in the encoder, or NOP that check (spell combos use it).
5. The alternative (hard, not recommended): a 16x15 glyph cache hook in MenuDrawChar. It clashes with the 12-px row pitch and the 128-px name width, and needs a VRAM cache plus upload code.

### Step 4: graphics and the rest
- **F_GAME graphics:** K's Korean logo (F_GAME 0x2C000–0x2FFFF) can be copied 1:1. "LEVEL UP", "Now Loading" and similar need new pixel art in F_GAME / F_GAME2.
- **Overlay side (separate task):** item pickup names (they read `g_api.equipDefs` names, so the new encoding must match their blitter, which uses the same 8x8 sheet), relic orb banner, Faerie Scroll name display (find it by read-watch), LIB shop.

---

## 4. Recommended order and difficulty

| Order | Work | Difficulty | Code change |
|---|---|---|---|
| 1 | Engine B data: descriptions, relic/spell names, system help, save messages | Easy | None; repoint strings only |
| 2 | Engine C labels: ATT/DEF, menus, categories, slots | Easy–medium | ~20-instruction stub + MenuDrawStr 0xFE prefix hook |
| 3 | Engine A: item names, menu words, enemy names via the K sheet | Medium | 1 instruction + F_GAME block swap + encoder |
| 4 | Graphics (logo, LEVEL UP …) and overlay-side item/relic pop-ups | Medium–hard | Separate (overlays) |

