# Static overworld map16 overlays written by the generator.
#
# In-game loader (Overworld_LoadNewTiles) applies this table first from bank $A3,
# then the dynamic OverworldMapChangePointers table. Seed-known overlays belong
# here; true runtime event checks / custom commands stay dynamic.
#
# Layout at SNES $A3B000 (PC $11B000):
#   - word pointers for screens $00..$81 (0x82 entries); $0000 = no changes
#   - packed overlay payloads (same encoding as the dynamic overlays)
#
# Each screen is assembled independently: every matching change(...) unit for that
# screen is concatenated in declaration order, then overlay() terminates once.
# Mixed reasons on one screen are just multiple change() entries with different
# when/param pairs (flip, glitch, disabled edge, etc.).

from enum import IntEnum
from typing import NamedTuple, Optional

from Utils import int16_as_bytes, snes_to_pc

# ---------------------------------------------------------------------------------------------------
# Addresses / layout

STATIC_MAP_SNES = 0xA3B000
NUM_SCREENS = 0x82
POINTER_TABLE_BYTES = NUM_SCREENS * 2  # 0x104
DATA_START_OFFSET = POINTER_TABLE_BYTES  # payloads pack immediately after the pointer table

# ---------------------------------------------------------------------------------------------------
# Inclusion rules

class ChangeWhen(IntEnum):
    """
    Condition family for a change unit. Optional string `param` refines the rule.

    FLIPPED param:
      None        — screen is flipped
      'noglitch'  — flipped and not OW-glitch logic (WarningFlags $20 skip)
      'glitched'  — flipped and OW-glitch logic

    OWLAYOUT param:
      None        — OW layout/crossed/mixed modes that set OWTileMapAlt bit $02
      'lw'        — same, and screen is light-world-like (OWTileWorldAssoc without $40)

    ATGT param:
      'swapped'   — Agahnim Tower / Ganon Tower swapped
      'vanilla'   — not swapped
    """
    ALWAYS = 0
    FLIPPED = 1
    UNFLIPPED = 2
    ATGT = 3
    GLITCHED = 4
    OWLAYOUT = 5


class Change(NamedTuple):
    when: ChangeWhen
    words: list
    param: Optional[str] = None


def change_applies(change, world, player, screen):
    when = change.when
    param = change.param
    flipped = world.is_tile_swapped(screen, player)
    glitched = world.logic[player] in ['owglitches', 'hybridglitches', 'nologic']

    if when == ChangeWhen.ALWAYS:
        return True

    if when == ChangeWhen.FLIPPED:
        if not flipped:
            return False
        if param is None:
            return True
        if param == 'noglitch':
            return not glitched
        if param == 'glitched':
            return glitched
        raise ValueError(f"Unknown FLIPPED param {param!r} on screen {screen:#x}")

    if when == ChangeWhen.UNFLIPPED:
        return not flipped

    if when == ChangeWhen.GLITCHED:
        return glitched

    if when == ChangeWhen.OWLAYOUT:
        if not (world.owLayout[player] != 'vanilla'
                or world.owCrossed[player] not in ['none', 'polar']
                or world.owMixed[player]):
            return False
        if param is None:
            return True
        if param == 'lw':
            return world.is_tile_lw_like(screen, player)
        raise ValueError(f"Unknown OWLAYOUT param {param!r} on screen {screen:#x}")

    if when == ChangeWhen.ATGT:
        swapped = world.is_atgt_swapped(player)
        if param == 'swapped':
            return swapped
        if param == 'vanilla':
            return not swapped
        raise ValueError(f"ATGT requires param 'swapped' or 'vanilla' on screen {screen:#x}")

    return False

# ---------------------------------------------------------------------------------------------------
# Overlay command encoding (mirrors invertedmaps.asm)

OWW_END = 0xFFFF
OWW_STOP = 0x8000
OWW_SKIP = 0xFFFF
OWW_VERTICAL = 0x0080
OWW_HORIZONTAL = 0x0000

OWW_STRIPE = 0x8000
OWW_STRIPE_RLE = 0x8001
OWW_STRIPE_RLE_INC = 0x8002
OWW_ARB_TILE_COPY = 0x8003


def oww_rle_size(size):
    return (size & 0x7F) << 8


def tile(tile_id, pos):
    """Single map16 write: dw <tile>, <pos>."""
    return [tile_id & 0xFFFF, pos & 0xFFFF]


def end():
    return [OWW_END]


def stripe(start, tiles, vertical=False):
    """
    Stripe of unique tiles; final tile is OR'd with OWW_STOP.

    Entries equal to OWW_SKIP leave a gap (bit 15 set, ASM continues without
    writing). SKIP is never OR'd with STOP.
    """
    if not tiles:
        raise ValueError('stripe requires at least one tile')
    direction = OWW_VERTICAL if vertical else OWW_HORIZONTAL
    words = [OWW_STRIPE | direction, start & 0xFFFF]
    last = len(tiles) - 1
    for i, t in enumerate(tiles):
        value = t & 0xFFFF
        if value == OWW_SKIP:
            words.append(OWW_SKIP)
        elif i == last:
            words.append(value | OWW_STOP)
        else:
            words.append(value)
    return words


def stripe_rle(tile_id, start, size, vertical=False):
    direction = OWW_VERTICAL if vertical else OWW_HORIZONTAL
    return [
        OWW_STRIPE_RLE | direction | oww_rle_size(size),
        tile_id & 0xFFFF,
        start & 0xFFFF,
    ]


def stripe_rle_inc(tile_id, start, size, vertical=False):
    direction = OWW_VERTICAL if vertical else OWW_HORIZONTAL
    return [
        OWW_STRIPE_RLE_INC | direction | oww_rle_size(size),
        tile_id & 0xFFFF,
        start & 0xFFFF,
    ]


def arb_tile_copy(tile_id, positions):
    """Write the same tile to each position; final pos is OR'd with OWW_STOP."""
    if not positions:
        raise ValueError('arb_tile_copy requires at least one position')
    words = [OWW_ARB_TILE_COPY, tile_id & 0xFFFF]
    for i, pos in enumerate(positions):
        value = pos & 0xFFFF
        if i == len(positions) - 1:
            value |= OWW_STOP
        words.append(value)
    return words


def overlay(*parts):
    """
    Flatten overlay fragments into a single screen payload, terminating with END.

    Applied at the screen-assembly layer after selecting which change units apply,
    so multiple sources/reasons can contribute fragments to the same screen.
    """
    words = []
    for part in parts:
        words.extend(part)
    if not words or words[-1] != OWW_END:
        words.append(OWW_END)
    return words

# ---------------------------------------------------------------------------------------------------
# Change units

def change(when, *parts, param=None):
    """
    Bundle tile-change fragments under a condition.

    when   — ChangeWhen family
    param  — optional string refining the condition (see ChangeWhen)
    parts  — fragment word lists from tile()/stripe()/...

    Does not append END; overlay() is applied when the screen is assembled.
    """
    words = []
    for part in parts:
        words.extend(part)
    return Change(when, words, param)


def build_screen_overlay(screen, world, player):
    """
    Build the static overlay word list for a single screen, or None if empty.

    Walks that screen's change units in order, keeps those whose when/param
    apply for this seed, then wraps with overlay().
    """
    units = SCREEN_CHANGES.get(screen)
    if not units:
        return None

    parts = []
    for unit in units:
        if unit.words and change_applies(unit, world, player, screen):
            parts.append(unit.words)
    if not parts:
        return None
    return overlay(*parts)

# ---------------------------------------------------------------------------------------------------
# Table build / ROM write

def _words_to_bytes(words):
    data = []
    for word in words:
        data.extend(int16_as_bytes(word & 0xFFFF))
    return data


def build_static_map_table(world, player):
    """
    Build the full static overlay blob: pointer table + payloads.

    Screens are assembled independently via build_screen_overlay, then packed
    in screen-id order immediately after the pointer table.

    Returns (blob_bytes, screen_pointer_snes_addrs) where the second value maps
    screen id -> SNES address of that screen's payload (or 0 if none).
    """
    screen_payloads = {}
    for screen in range(NUM_SCREENS):
        words = build_screen_overlay(screen, world, player)
        if words:
            screen_payloads[screen] = _words_to_bytes(words)

    pointers = [0] * NUM_SCREENS
    data = bytearray()
    cursor = DATA_START_OFFSET
    for screen in sorted(screen_payloads):
        payload = screen_payloads[screen]
        snes_addr = (STATIC_MAP_SNES + cursor) & 0xFFFF
        pointers[screen] = snes_addr
        data.extend(payload)
        cursor += len(payload)

    blob = bytearray()
    for ptr in pointers:
        blob.extend(int16_as_bytes(ptr))
    blob.extend(data)
    return bytes(blob), pointers


def write_static_map_changes(rom, world, player):
    """Write OverworldStaticMapPointers (+ payloads) to the fixed ROM location."""
    blob, _ = build_static_map_table(world, player)
    rom.write_bytes(snes_to_pc(STATIC_MAP_SNES), blob)
    return len(blob)

# ---------------------------------------------------------------------------------------------------
# Per-screen change units
#
# A screen is an ordered list of change(when, *fragments, param=...). Mixed
# types on one screen are separate units; only matching units are emitted, in
# list order, then overlay() terminates the payload.
#
# Runtime-only leftovers stay in invertedmaps.asm (event flags, custom commands).

SCREEN_CHANGES = {
    0x03: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x034, 0x2BE0),
        ),
        change(ChangeWhen.FLIPPED,  # spectacle rock
            stripe(0x29B6, [0x21A, 0x1F3, 0x0A0, 0x104]),
            arb_tile_copy(0x0C6, [0x2A34, 0x2A38, 0x2A3A]),
            param='noglitch',
        ),
    ],
    0x05: [
        change(ChangeWhen.ALWAYS,
            tile(0x101, 0x2E18),  # OWG sign
        ),
        change(ChangeWhen.FLIPPED,
            tile(0x034, 0x3D4A),  # portal
        ),
        change(ChangeWhen.FLIPPED,
            # spiral/mimic ledge hops
            tile(0x139, 0x2C6C),
            tile(0x14B, 0x2C6E),
            tile(0x16B, 0x29F0),
            tile(0x16B, 0x2CEC),
            tile(0x182, 0x29F2),
            tile(0x182, 0x2CEE),

            # floating island
            tile(0x034, 0x21F2),
            tile(0x116, 0x216E),
            tile(0x126, 0x21F4),
            stripe(0x206E, [0x111, 0x113, 0x113, 0x112]),
            stripe_rle_inc(0x111, 0x20EC, 2),
            stripe_rle_inc(0x116, 0x20F0, 3),
            stripe(0x216C, [0x112, 0x116, 0x11C, 0x11D, 0x11E]),
            stripe_rle_inc(0x11C, 0x2170, 3),
            stripe_rle_inc(0x123, 0x21EC, 2),
            stripe_rle_inc(0x144, 0x2364, 4),
            stripe_rle_inc(0x1B3, 0x236C, 2),
            stripe(0x2970, [0x139, 0x14B]),
            arb_tile_copy(0x130, [0x21E2, 0x21F0, 0x22E2, 0x22F0]),
            arb_tile_copy(0x135, [0x2262, 0x2270, 0x2362, 0x2370]),
            arb_tile_copy(0x136, [0x2264, 0x2266, 0x226C, 0x226E]),
            arb_tile_copy(0x137, [0x2268, 0x226A]),
            stripe(0x22E4, [0x13C, 0x13C, 0x13D, 0x13D, 0x13C, 0x13C]),
            param='noglitch',
        ),
        change(ChangeWhen.FLIPPED,  # spiral/mimic bridge connection
            stripe_rle(0x0E3, 0x2BDC, 8),
            stripe_rle(0x14E, 0x2C5C, 2),
            stripe_rle(0x14E, 0x2C64, 4),
            stripe(0x2C60, [0x139, 0x14B]),
            stripe_rle(0x152, 0x2CDC, 2),
            stripe_rle(0x152, 0x2CE4, 4),
            stripe(0x2CE0, [0x16B, 0x182]),
            stripe_rle(0x22E, 0x2D5C, 8),
            stripe_rle(0x230, 0x2DDC, 3),
            stripe_rle(0x230, 0x2DE6, 3),
            stripe_rle(0x2A6, 0x2DE2, 2),
        ),
    ],
    0x07: [
        change(ChangeWhen.FLIPPED,  # TR peg ledge barrier
            stripe(0x251C, [0x163, 0x0152, 0x0152, 0x0152, 0x0152, 0x01F2]),
            stripe(0x259A, [0x163, 0x11C, 0x11D, 0x11D, 0x11D, 0x11D, 0x11E, 0x01F2]),
            stripe(0x2618, [0x163, 0x124, 0x124, 0x124, 0x124, 0x124, 0x140], vertical=True),
            stripe(0x262A, [0x1F2, 0x127, 0x127, 0x127, 0x127, 0x127, 0x150], vertical=True),
            stripe(0x299A, [0x161, 0x141, 0x14E, 0x14E, 0x14E, 0x14E, 0x14F, 0x150]),
            arb_tile_copy(0x125, [0x261C, 0x269A]),
            arb_tile_copy(0x126, [0x2626, 0x26A8]),
            arb_tile_copy(0x139, [0x289A, 0x291C]),
            arb_tile_copy(0x14B, [0x28A8, 0x2926]),
            arb_tile_copy(0x152, [0x2A1E, 0x2A24]),
            tile(0x11C, 0x261A),
            tile(0x11E, 0x2628),
            tile(0x0CE, 0x2896),
            tile(0x16A, 0x28AC),
            tile(0x141, 0x291A),
            tile(0x14F, 0x2928),
            tile(0x161, 0x2A1C),
            tile(0x150, 0x2A26),
            tile(0x21B, 0x2620),  # moved peg
        ),
    ],
    0x10: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x034, 0x2B2E),
        ),
    ],
    0x14: [
        change(ChangeWhen.FLIPPED,  # graveyard ladder
            stripe(0x2422, [0x2F1, 0x184, 0x184], vertical=True),
            stripe(0x2424, [0x2F2, 0x185, 0x185], vertical=True),
            param='noglitch',
        ),
    ],
    0x1A: [
        change(ChangeWhen.OWLAYOUT,  # rocks for hardlock protection
            stripe_rle_inc(0x2F8, 0x2FBC, 2),
        ),
    ],
    0x1B: [
        change(ChangeWhen.OWLAYOUT,  # rocks for hardlock protection
            stripe(0x2FFE, [0x39A, 0x39B], vertical=True),
            stripe(0x2F80, [0x2FA, 0x30A, 0x30D], vertical=True),
        ),
        change(ChangeWhen.FLIPPED,
            tile(0x101, 0x2252),  # goal sign
            arb_tile_copy(0x46D, [0x243E, 0x24BC, 0x24BE, 0x253E, 0x2440, 0x24C0, 0x24C2, 0x2540]),  # eye removed

            # new trees
            stripe(0x2DAA, [0x034, 0x4BA, 0x4BB, 0x034], vertical=True),
            stripe(0x2DB0, [0x034, 0x4BA, 0x4BB, 0x034], vertical=True),

            # new HC door
            stripe_rle(0x44F, 0x201C, 2),
            stripe_rle(0x455, 0x209C, 2),
            stripe_rle_inc(0x45A, 0x211A, 4),
            stripe_rle_inc(0x463, 0x219A, 4),
        ),
        change(ChangeWhen.ATGT,
            tile(0x101, 0x222C),  # tower entry sign
            param='swapped',
        ),
    ],
    0x22: [
        change(ChangeWhen.OWLAYOUT,  # rocks for hardlock protection
            tile(0x2B9, 0x203C),
            tile(0x309, 0x203E),
            tile(0x30E, 0x20BE),
        ),
    ],
    0x29: [
        change(ChangeWhen.FLIPPED,  # bush relocated
            tile(0x034, 0x248A),
            tile(0x036, 0x2386),
        ),
    ],
    # 0x2F: [
    #     change(ChangeWhen.FLIPPED,  # portal
    #         tile(0x034, 0x2BB2),
    #     ),
    # ],
    0x30: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x034, 0x3D94),
        ),
        change(ChangeWhen.FLIPPED,  # checkerboard cave mods
            stripe_rle(0x0D1, 0x2052, 6),
            stripe_rle(0x0C9, 0x20D2, 6),
            stripe_rle(0x0DC, 0x2152, 6),
            stripe_rle(0x0D1, 0x2266, 6),
            stripe_rle(0x721, 0x22E6, 6),
            stripe_rle(0x0CC, 0x2366, 6),
            stripe_rle(0x384, 0x25E6, 4),
            stripe_rle(0x6B4, 0x2662, 8),
            stripe_rle(0x165, 0x26E0, 9),
            stripe(0x2460, [0x0A3, 0x0D5, 0x0C5, 0x63D, 0x384, 0x0AB, 0x384]),
            stripe(0x2552, [0x6E5, 0x63D, 0x6AB, 0x109, 0x6AA, 0x6AA, 0x6AA, 0x10C, 0x106, 0x107, 0x6AB, 0x384]),
            stripe(0x25D2, [0x6E5, 0x6AB, 0x109, 0x10C, 0x6A7, 0x6A7, 0x6A7, 0x106, 0x107, 0x6AB]),
            stripe(0x2652, [0x6E5, 0x6AB, 0x10C, 0x105, 0x106, 0x165, 0x166, 0x766]),
            stripe(0x24E0, [0x109, 0x0D5, 0x0C5]),
            stripe(0x224C, [0x0DC, 0x0C9, 0x386, 0x759], vertical=True),
            stripe(0x21CE, [0x153, 0x153, 0x153, 0x256, 0x757, 0x759], vertical=True),
            stripe(0x2150, [0x153, 0x178, 0x153, 0x256, 0x6AB, 0x6AB, 0x757, 0x759], vertical=True),
            stripe(0x26D2, [0x6E5, 0x6E5, 0x6E5, 0x759], vertical=True),
            stripe(0x26D6, [0x0D5, 0x0D5, 0x0D5, 0x0D5, 0x1E9], vertical=True),
            stripe(0x26D8, [0x0C4, 0x0CF, 0x302, 0x0C5], vertical=True),
            stripe(0x20DE, [0x0D0, 0x0C8, 0x0CA, 0x0C8, 0x0DB], vertical=True),
            stripe(0x2160, [0x0D0, 0x0C8, 0x0CA, 0x0C8, 0x0DB, 0x09E], vertical=True),
            stripe(0x21E2, [0x0D0, 0x0C8, 0x0CA, 0x0D3, 0x0CE], vertical=True),
            stripe(0x2264, [0x0D0, 0x0C8, 0x302, 0x0C5], vertical=True),
            arb_tile_copy(0x6AB, [0x23D2, 0x23E6, 0x2452, 0x2454, 0x24D4, 0x24E6, 0x26D4, 0x2754, 0x27D4]),
            arb_tile_copy(0x0D2, [0x205E, 0x20E0, 0x2162, 0x21E4, 0x275C]),
            arb_tile_copy(0x17E, [0x2050, 0x20CE]),
            arb_tile_copy(0x183, [0x20D0, 0x214E]),
            arb_tile_copy(0x384, [0x24D8, 0x24EA]),
            arb_tile_copy(0x757, [0x24D2, 0x2854]),
            tile(0x0AB, 0x2352),
            tile(0x171, 0x26DE),
            tile(0x759, 0x28D4),
            param='noglitch',
        ),
    ],
    0x32: [
        change(ChangeWhen.FLIPPED,  # cave 45 mods
            tile(0x1D5, 0x2486),
            tile(0x165, 0x2506),
            tile(0x166, 0x2508),
            tile(0x220, 0x278C),
            tile(0x75E, 0x299A),
            tile(0x0AB, 0x299C),
            tile(0xBDB, 0x2C0A),
            stripe(0x2586, [0x0C6, 0x171, 0x166]),
            stripe(0x2A1A, [0x75F, 0x0C6, 0x1E5, 0x77E]),
            stripe(0x2A9A, [0x775, 0x1E5, 0x77E, 0x106, 0x165]),
            stripe(0x2B1A, [0x75F, 0x77E, 0x106, 0x107, 0x0C6]),
            stripe(0x2B9C, [0x0D5, 0x0C5, 0x0C6]),
            stripe_rle(0x09F, 0x2812, 4),
            stripe_rle(0x6E1, 0x2890, 4),
            stripe_rle(0x034, 0x29A2, 4),
            stripe_rle(0x0C6, 0x2608, 4, vertical=True),
            stripe_rle(0x21C, 0x260A, 4, vertical=True),
            arb_tile_copy(0x167, [0x2488, 0x250A, 0x258C, 0x2A28, 0x2AAA, 0x2B2C, 0x2BAE]),
            arb_tile_copy(0x160, [0x248A, 0x250C, 0x2A2A, 0x2AAC, 0x2B2E]),
            arb_tile_copy(0x17C, [0x270E, 0x2790, 0x281A, 0x289C, 0x291E, 0x29A0]),
            arb_tile_copy(0x1FF, [0x278E, 0x2810, 0x289A, 0x291C, 0x299E]),
            arb_tile_copy(0x757, [0x280E, 0x2898, 0x291A]),
            arb_tile_copy(0x034, [0x281C, 0x289E, 0x2920]),
            arb_tile_copy(0x759, [0x288E, 0x2918, 0x2B9A]),
            arb_tile_copy(0x2EC, [0x2A8A, 0x2A8E, 0x2A92, 0x2A94, 0x2A96, 0x2C0C]),
            arb_tile_copy(0x789, [0x2B0A, 0x2B0E, 0x2B14, 0x2B94]),
            arb_tile_copy(0x2EB, [0x2B12, 0x2B16, 0x2C8C, 0x2C94]),
            arb_tile_copy(0xBDC, [0x2B8A, 0x2B8E, 0x2C0E, 0x2C14]),
            param='noglitch',
        ),
    ],
    # 0x33: [
    #     change(ChangeWhen.FLIPPED,  # portal
    #         tile(0x034, 0x22A8),
    #     ),
    # ],
    0x35: [
        change(ChangeWhen.FLIPPED,
            tile(0x034, 0x2F56),  # portal
        ),
        change(ChangeWhen.FLIPPED,  # lake hylia island ladder
            stripe(0x2BB0, [0x2F1, 0x184, 0x392, 0x394], vertical=True),
            stripe(0x2BB2, [0x2F2, 0x185, 0x393, 0x395], vertical=True),
            param='noglitch',
        ),
    ],
    0x3A: [
        change(ChangeWhen.FLIPPED,  # bombos tablet ladder
            tile(0x964, 0x2984),
            tile(0x17E, 0x2986),
            stripe_rle(0x184, 0x2A04, 4, vertical=True),
            stripe_rle(0x185, 0x2A06, 4, vertical=True),
            param='noglitch',
        ),
    ],
    0x3F: [
        change(ChangeWhen.OWLAYOUT,  # C terrain
            stripe_rle_inc(0x75C, 0x2A9A, 2, vertical=True),
            stripe(0x2A22, [0x752, 0x753, 0x2E5]),
            stripe(0x2A9E, [0x774, 0x6E1, 0x757, 0x6E3, 0x2E5]),
            stripe(0x2B1E, [0x76E, 0x2E5, 0x759, 0x779]),
            stripe(0x2B9E, [0x76C, 0x2EC, 0x6F5, 0x705]),
            stripe(0x2C1E, [0x704, 0x6F6, 0x6F7, 0x6E3]),
            stripe(0x2CA2, [0x762, 0x773]),
            arb_tile_copy(0x2EC, [0x29A4, 0x2C16]),
            tile(0x75E, 0x2B9A),
            tile(0x76F, 0x2C1A),
            param='lw',
        ),
    ],
    0x43: [
        change(ChangeWhen.ATGT,
            tile(0x101, 0x2550),  # gt entry sign
            param='vanilla',
        ),
        change(ChangeWhen.ATGT,  # gt entrance auto-opened
            stripe(0x235E, [0x8D5, 0x8E3, 0xE90, 0xE96, 0xE96, 0xE94], vertical=True),
            stripe(0x2360, [0x8D6, 0x8E4, 0xE91, 0xE97, 0xE97, 0xE95], vertical=True),
            param='swapped',
        ),
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x212, 0x2BE0),
        ),
    ],
    0x45: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x239, 0x3D4A),
        ),
    ],
    0x47: [
        change(ChangeWhen.FLIPPED,  # portals
            tile(0x239, 0x269E),
            tile(0x239, 0x26A4),
        ),
        change(ChangeWhen.FLIPPED,  # turtle tail hop
            tile(0x398, 0x25A0),
            tile(0x522, 0x25A2),
            tile(0x125, 0x2620),
            tile(0x126, 0x2622),
            param='noglitch',
        ),
    ],
    0x50: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x20F, 0x2B2E),
        ),
    ],
    0x5A: [
        change(ChangeWhen.OWLAYOUT,  # rocks for hardlock protection
            stripe_rle_inc(0x2F8, 0x2FBC, 2),
        ),
    ],
    0x5B: [
        change(ChangeWhen.OWLAYOUT,  # rocks for hardlock protection
            stripe(0x2F80, [0x2FA, 0x30A, 0x30D], vertical=True),
            stripe_rle_inc(0x39A, 0x2FFE, 2, vertical=True),
        ),
        change(ChangeWhen.UNFLIPPED,  # sign/peg
            tile(0x101, 0x27B6),
            tile(0x5C2, 0x27B4),
        ),
        change(ChangeWhen.FLIPPED,
            stripe(0x2E1C, [0xA06, 0xA0E]),  # seal pyramid entrance

            # south pyramid terrain
            tile(0x323, 0x39B6),
            stripe_rle(0x324, 0x39B8, 4),
            tile(0x2FE, 0x3A34),
            tile(0x2FF, 0x3A36),
            tile(0x235, 0x3BB4),
            stripe_rle(0x326, 0x3A38, 4),
            stripe(0x3AB2, [0x39D, 0x303, 0x232, 0x233, 0x233, 0x233, 0x233]),
            stripe(0x3B32, [0x3A2, 0x232, 0x235, 0x46A, 0x333, 0x333, 0x333]),
            arb_tile_copy(0x034, [0x3BB6, 0x3BBA, 0x3BBC, 0x3C3A, 0x3C3C, 0x3C3E]),
            tile(0x0F2, 0x3BB8),
            tile(0x108, 0x3C38),
            stripe(0x39C0, [0x324, 0x324, 0x324, 0x325, 0x2D5, OWW_SKIP, 0x2CC]),
            tile(0x2CC, 0x39D4),
            stripe(0x3A40, [0x326, 0x326, 0x326, 0x327, 0x2F7, OWW_SKIP, 0x2E3, 0x2E3]),
            stripe(0x3AC0, [0x233, 0x233, 0x233, 0x234, 0x2F6, 0x396]),
            stripe(0x3B40, [0x333, 0x333, 0x3AA, 0x3A3, 0x234, 0x397]),
            stripe(0x3BC0, [0x034, 0x034, 0x29C, 0x034, 0x3A3]),
            stripe(0x3C40, [0x034, 0x034, 0x10A]),
            stripe_rle(0x10B, 0x3C46, 17),
        ),
    ],
    0x62: [
        change(ChangeWhen.OWLAYOUT,  # rocks for hardlock protection
            tile(0x2B9, 0x203C),
            tile(0x309, 0x203E),
            tile(0x30E, 0x20BE),
        ),
    ],
    0x6F: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x20F, 0x2BB2),
        ),
    ],
    0x70: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x239, 0x3D94),
        ),
    ],
    0x73: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x20F, 0x22A8),
        ),
    ],
    0x75: [
        change(ChangeWhen.FLIPPED,  # portal
            tile(0x239, 0x3352),
        ),
    ],
    0x7F: [
        change(ChangeWhen.OWLAYOUT,  # C terrain
            stripe_rle_inc(0x75C, 0x2A9A, 2, vertical=True),
            stripe(0x2A22, [0x752, 0x753, 0x2E5]),
            stripe(0x2A9E, [0x774, 0x6E1, 0x757, 0x6E3, 0x2E5]),
            stripe(0x2B1E, [0x76E, 0x2E5, 0x759, 0x779]),
            stripe(0x2B9E, [0x76C, 0x2EC, 0x6F5, 0x705]),
            stripe(0x2C1E, [0x704, 0x6F6, 0x6F7, 0x6E3]),
            stripe(0x2CA2, [0x762, 0x773]),
            arb_tile_copy(0x2EC, [0x29A4, 0x2C16]),
            tile(0x75E, 0x2B9A),
            tile(0x76F, 0x2C1A),
            param='lw',
        ),
    ],
}
