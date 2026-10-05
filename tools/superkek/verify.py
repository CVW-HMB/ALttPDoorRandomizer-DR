import glob
import json
import os
import re
import sys

import yaml
from bps.apply import apply_to_files

# Verify finished seeds before publishing: patch applies, ROM hash (alttprasyncs icon names), key settings,
# HUD counter bytes, Triforce location, per-dungeon item / small key / key door counts.
# usage: verify.py <final dir> [<final dir> ...]   e.g. verify.py final_dec/DR_superkekpriest64_PB_3001
S = os.path.dirname(os.path.abspath(__file__))
ROM = os.path.join(S, '..', '..', 'Zelda no Densetsu - Kamigami no Triforce (Japan).sfc')
# z3randomizer hash icon order -> option names on alttprasyncs.com
SITE = ['Bow', 'Boomerang', 'Hookshot', 'Bombs', 'Mushroom', 'Magic Powder', 'Ice Rod', 'Pendant', 'Bombos', 'Ether',
        'Quake', 'Lamp', 'Hammer', 'Shovel', 'Flute', 'Bugnet', 'Book', 'Empty Bottle', 'Green Potion', 'Somaria',
        'Cape', 'Mirror', 'Boots', 'Gloves', 'Flippers', 'Moon Pearl', 'Shield', 'Tunic', 'Heart', 'Map', 'Compass',
        'Big Key']
KEYNAME = {'Hyrule Castle': 'Escape'}
SETTINGS = ['Mode', 'Door Shuffle', 'Intensity', 'Decouple Doors', 'Pseudoboots', 'Small Key shuffle', 'Big Key shuffle',
            'Map shuffle', 'Compass shuffle', 'Boss shuffle', 'Enemy shuffle', 'Enemy logic', 'Key Logic Algorithm',
            'Trap Door Mode', 'Pottery Mode']

for d in sys.argv[1:]:
    d = d.rstrip('/')
    log = f'{d}/log.txt'
    if os.path.exists(log) and 'Total Time' not in open(log).read():
        print(f'== {os.path.basename(d)}\n   ROLL FAILED (see {log}): do not publish')
        continue
    bps = glob.glob(f'{d}/*.bps')[0]
    patched = f'{d}/verify.sfc'
    with open(ROM, 'rb') as s, open(bps, 'rb') as p, open(patched, 'wb') as o:
        apply_to_files(p, s, o)
    rom = open(patched, 'rb').read()
    os.remove(patched)
    sp = open(glob.glob(f'{d}/*Spoiler.txt')[0]).read()
    st = {}
    for k in SETTINGS:
        m = re.search(rf'^{k}[^:\n]*:\s*(.*)$', sp, re.M | re.I)
        st[k] = m.group(1).strip().strip("'").strip() if m else '?'
    sanc = re.search(r'^Sanctuary @ [^:]+: (.*)$', sp, re.M)
    locs = json.load(open(f'{d}/locs.json'))
    custom = yaml.safe_load(open(glob.glob(f'{d}/*_custom.yaml')[0]))
    placed = custom['placements'][1]
    # item_pool is recorded before money balancing, placements after: a higher Rupees (300) count means money spawned
    pool300 = custom.get('item_pool', {}).get(1, {}).get('Rupees (300)', 0)
    placed300 = sum(1 for i in placed.values() if i == 'Rupees (300)')
    door_types = sp[sp.index('Door Types:'):] if 'Door Types:' in sp else ''
    key_doors = {}
    for m in re.finditer(r'\(([A-Za-z ]+)\) Key Door$', door_types, re.M):
        key_doors[m.group(1)] = key_doors.get(m.group(1), 0) + 1
    print(f'== {os.path.basename(d)}')
    print(f'   bps {os.path.basename(bps)} ({os.path.getsize(bps)} bytes) -> rom {len(rom)} bytes')
    print(f'   hash (site names): {", ".join(SITE[c & 0x1f] for c in rom[0x180215:0x18021a])}')
    print(f'   spoiler hash:      {re.search(r"^Hash:\s*(.*)$", sp, re.M).group(1)}')
    print(f'   HUD dungeon counters 0x18003A={rom[0x18003A]} 0x18003C={rom[0x18003C]} (2 = always on)')
    print(f'   Sanctuary chest: {sanc.group(1) if sanc else "?"}')
    print(f'   money spawned: {"none" if placed300 <= pool300 else f"YES ({placed300 - pool300} extra Rupees (300))"} (pool {pool300}, placed {placed300})')
    for k, v in st.items():
        print(f'   {k}: {v}')
    print(f'   world locations: {len(placed)}')
    for dn, ls in sorted(locs.items(), key=lambda x: -len(x[1])):
        keys = sum(1 for l, i in placed.items() if i == f'Small Key ({KEYNAME.get(dn, dn)})')
        print(f'   {dn:20s} items={len(ls):4d} small_keys={keys:3d} key_doors={key_doors.get(dn, 0)}')
