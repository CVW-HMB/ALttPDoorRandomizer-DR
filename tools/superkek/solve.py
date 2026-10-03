import json, sys, itertools
from collections import defaultdict

d = json.load(open(sys.argv[1]))
sectors = d['sectors']
portal_info = {p['name']: p for p in d['portals']}

AX = {('Normal', 'North'): 0, ('Normal', 'South'): 0, ('Normal', 'East'): 1, ('Normal', 'West'): 1,
      ('SpiralStairs', 'Up'): 2, ('SpiralStairs', 'Down'): 2, ('Open', 'North'): 3, ('Open', 'South'): 3,
      ('Open', 'East'): 4, ('Open', 'West'): 4, ('StraightStairs', 'North'): 5, ('StraightStairs', 'South'): 5,
      ('Ladder', 'North'): 6, ('Ladder', 'South'): 6}
SIGN = {'North': 1, 'South': -1, 'East': 1, 'West': -1, 'Up': 1, 'Down': -1}


import os
SELF_LOOPS = bool(os.environ.get('SELF_LOOPS'))


def vec(doors):
    v = [0] * 7
    for x in doors:
        if SELF_LOOPS and x['type'] == 'SpiralStairs':
            continue
        v[AX[(x['type'], x['dir'])]] += SIGN[x['dir']]
    return tuple(v)


def find(region):
    for i, s in enumerate(sectors):
        if region in s['regions']:
            return i
    raise KeyError(region)


# all doors of a sector including any portal door currently attached to the overworld
def all_doors(s):
    names = {x['name'] for x in s['doors']}
    extra = [{'name': p, 'type': 'Normal', 'dir': 'South'} for p in s['portal_doors'] if p not in names]
    return s['doors'] + extra


for s in sectors:
    s['all'] = all_doors(s)

# sectors locked to a specific dungeon
locked = {}
boss = {'Eastern Palace': ['Eastern Boss'], 'Desert Palace': ['Desert Boss'], 'Tower of Hera': ['Hera Boss'],
        'Palace of Darkness': ['PoD Boss'], 'Swamp Palace': ['Swamp Boss'],
        'Skull Woods': ['Skull Boss', 'Skull Pinball', 'Skull Left Drop', 'Skull Pot Circle', 'Skull Back Drop'],
        'Thieves Town': ['Thieves Boss', "Thieves Blind's Cell"], 'Ice Palace': ['Ice Boss'],
        'Misery Mire': ['Mire Boss'], 'Turtle Rock': ['TR Boss'], 'Ganons Tower': ['GT Agahnim 2'], 'Agahnims Tower': ['Tower Agahnim 1']}
for dn, regs in boss.items():
    for r in regs:
        locked[find(r)] = dn
for r in ['Hyrule Dungeon Cellblock', 'Sanctuary', 'Hyrule Castle Throne Room', 'Sewers Rat Path']:
    locked[find(r)] = 'HC/AT'

# portal count, and groups of portal labels that need at least one walk-through passage
spec = {
    'Eastern Palace': (['Eastern'], []),
    'Desert Palace': (['Desert South', 'Desert West', 'Desert Back', 'Desert East'], [['Desert East']]),
    'Tower of Hera': (['Hera'], []),
    'Palace of Darkness': (['Palace of Darkness'], []),
    'Swamp Palace': (['Swamp'], []),
    'Skull Woods': (['Skull 1', 'Skull 2 East', 'Skull 2 West', 'Skull 3'], [['Skull 2 West', 'Skull 3']]),
    'Thieves Town': (['Thieves Town'], []),
    'Ice Palace': (['Ice'], []),
    'Misery Mire': (['Mire'], []),
    'Turtle Rock': (['Turtle Rock Main', 'Turtle Rock Lazy Eyes', 'Turtle Rock Chest', 'Turtle Rock Eye Bridge'],
                    [['Turtle Rock Eye Bridge'], ['Turtle Rock Chest', 'Turtle Rock Lazy Eyes']]),
    'Ganons Tower': (['Ganons Tower'], []),
    'Agahnims Tower': (['Agahnims Tower'], []),
}


PREFIX = {'Eastern Palace': 'Eastern', 'Desert Palace': 'Desert', 'Tower of Hera': 'Hera', 'Palace of Darkness': 'PoD',
          'Swamp Palace': 'Swamp', 'Skull Woods': 'Skull', 'Thieves Town': 'Thieves', 'Ice Palace': 'Ice',
          'Misery Mire': 'Mire', 'Turtle Rock': 'TR', 'Ganons Tower': 'GT', 'Agahnims Tower': 'Tower'}


def items_for(i):
    s = sectors[i]
    out = [(i, None, vec(s['all']))]
    for p in s['portal_doors']:
        rest = [x for x in s['all'] if x['name'] != p]
        out.append((i, p, vec(rest)))
    return out


def rooms_of(idxs):
    r = set()
    for i in idxs:
        r.update(sectors[i]['rooms'])
    return len(r)


def check(dn, chosen):
    labels, passages = spec[dn]
    k = len(labels)
    portals = [(i, p) for i, p, v in chosen if p]
    if len(portals) != k:
        return None
    if len({sectors[i]['rooms'][0] if sectors[i]['rooms'] else i for i, p in portals}) != k:
        return None
    net = [i for i, p, v in chosen if len(sectors[i]['all']) - (1 if p else 0) > 0]
    total_doors = sum(len(sectors[i]['all']) - (1 if p else 0) for i, p, v in chosen)
    if net and total_doors < 2 * (len(net) - 1):
        return None
    for i, p, v in chosen:
        s = sectors[i]
        if s['blue_barrier'] and not any(sectors[j]['c_switch'] for j, _, _ in chosen):
            return None
        if s['item_logic']:
            return None
    net_portals = [(i, p) for i, p in portals if i in net and portal_info[p]['passage']]
    dead = [(i, p) for i, p in portals if i not in net]
    # boss sector must contain a portal or be on the network
    for i, p, v in chosen:
        if i not in net and not p:
            return None
    # assign labels: each passage group needs one network portal, and the network needs another reachable portal
    need = len(passages)
    if net:
        if need and len(net_portals) < need + 1:
            return None
        if not any(p for i, p in portals if i in net):
            return None
    elif need:
        return None
    return portals, net, dead


def solve(dn, avoid, max_extra=4, want=5):
    req = [i for i, x in locked.items() if x == dn]
    pool = [i for i in range(len(sectors)) if i not in locked and i not in avoid]
    req_modes = [items_for(i) for i in req]
    extra_items = [it for i in pool for it in items_for(i)]
    sols = []
    for base in itertools.product(*req_modes):
        bv = [sum(x) for x in zip(*[b[2] for b in base])]
        for n in range(0, max_extra + 1):
            if sols and n > min(len(s[0]) for s in sols) - len(req) + 1:
                break
            for combo in itertools.combinations(extra_items, n):
                if len({c[0] for c in combo}) != n:
                    continue
                v = list(bv)
                for c in combo:
                    for a in range(7):
                        v[a] += c[2][a]
                if any(v):
                    continue
                chosen = list(base) + list(combo)
                r = check(dn, chosen)
                if r:
                    sols.append(([c[0] for c in chosen], chosen, r))
            if len(sols) > 2000:
                break
    pre = PREFIX[dn]
    def foreign(s):
        return sum(1 for i in s[0] if not any(r.startswith(pre) for r in sectors[i]['regions']))
    sols.sort(key=lambda s: (rooms_of(s[0]), foreign(s), sum(len(sectors[i]['regions']) for i in s[0])))
    return sols[:want]


if __name__ == '__main__':
    order = sys.argv[2].split(',') if len(sys.argv) > 2 else list(spec)
    used = set()
    for dn in order:
        sols = solve(dn, used, max_extra=int(sys.argv[3]) if len(sys.argv) > 3 else 2)
        print('==', dn, 'none' if not sols else '')
        for idxs, chosen, (portals, net, dead) in sols[:3]:
            print('  rooms', rooms_of(idxs))
            for i, p, v in chosen:
                s = sectors[i]
                print('    ', s['rooms'], s['regions'][:4], 'PORTAL ' + p if p else '',
                      [(x['name'], x['type'][:2], x['dir'][0]) for x in s['all'] if x['name'] != p])
        if sols:
            used.update(sols[0][0])
