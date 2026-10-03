import json
import os
import subprocess
import sys

# Rebuild solutions.json: every minimal room set for the 11 small dungeons, filtered down to the ones that
# survive DR's generator. Only needed when sectors.json or keycap.json change (new DR door data).
# usage: build_solutions.py   (run with the DR venv python, from anywhere)
S = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get('DR_PY', sys.executable)

raw = f'{S}/solutions_raw.json'
env = dict(os.environ, SELF_LOOPS='1', AVOID='[]', SKIP='["Agahnims Tower"]')
subprocess.run([PY, f'{S}/precompute.py', f'{S}/sectors.json', raw], cwd=S, env=env, check=True)

sectors = json.load(open(f'{S}/sectors.json'))['sectors']
portals = {p['name']: p for p in json.load(open(f'{S}/sectors.json'))['portals']}
keycap = json.load(open(f'{S}/keycap.json'))
sols = json.load(open(raw))


def all_doors(s):
    names = {x['name'] for x in s['doors']}
    return s['doors'] + [{'name': p, 'type': 'Normal', 'dir': 'South'} for p in s['portal_doors'] if p not in names]


interior_or_stair = {v['region'] for v in keycap.values() if v['type'] in ('Interior', 'SpiralStairs')}
stair = {v['region'] for v in keycap.values() if v['type'] == 'SpiralStairs'}


def regions(sol):
    return [r for i in sol['idxs'] for r in sectors[i]['regions']]


def keep(dn, sol):
    portal_of = {i: p for i, p in sol['chosen'] if p}
    # Swamp Hub as Swamp's lobby failed key analysis on DoorDevUnstable
    if dn == 'Swamp Palace' and 'Swamp Hub' in regions(sol):
        return False
    # a dead-end lobby door only works when it is the room's only door (Mire Right Bridge cannot reach Left Bridge)
    for i, p in sol['chosen']:
        if p and portals[p]['deadEnd'] and len(all_doors(sectors[i])) > 1:
            return False
    # no small key doors outside HC/AT: rooms with key-capable interior doors or stairs are out.
    # Skull and Thieves have mandatory rooms with key-capable interior doors (marked non-key by megagen
    # instead), so only their stairs are excluded. Hera always keeps its tower.
    if dn not in ('Tower of Hera', 'Skull Woods', 'Thieves Town') and any(r in interior_or_stair for r in regions(sol)):
        return False
    if dn in ('Skull Woods', 'Thieves Town') and any(r in stair for r in regions(sol)):
        return False
    # a room whose only exits are stairs gets self-looped into an island
    if dn != 'Tower of Hera' and len(sol['idxs']) > 1:
        for i in sol['idxs']:
            doors = [x for x in all_doors(sectors[i]) if x['name'] != portal_of.get(i)]
            if doors and not any(x['type'] != 'SpiralStairs' for x in doors):
                return False
    # the big key validator needs at least one ordinary location in the dungeon
    if dn != 'Tower of Hera':
        locs = [l for i in sol['idxs'] if not sectors[i]['boss'] for l in sectors[i]['locs']
                if 'Big Chest' not in l and 'Prize' not in l]
        if not locs:
            return False
    return True


out = {}
for dn, lst in sols.items():
    out[dn] = [s for s in lst if keep(dn, s)]
    best = min((s['rooms'] for s in out[dn]), default=None)
    print(f'{dn:20s} {len(lst):5d} -> {len(out[dn]):5d} solutions, min supertiles {best}')
json.dump(out, open(f'{S}/solutions.json', 'w'))
os.remove(raw)
