import sys, json, random, yaml

# usage: pick.py sectors.json solutions.json base.yaml seed out.yaml
d = json.load(open(sys.argv[1]))
sectors = d['sectors']
portal_info = {p['name']: p for p in d['portals']}
sols = json.load(open(sys.argv[2]))
base = yaml.safe_load(open(sys.argv[3]))
seed = int(sys.argv[4])
rng = random.Random(seed)
import os
OPEN = set(json.loads(os.environ.get('OPEN', '[]')))
SELF_LOOPS = bool(os.environ.get('SELF_LOOPS'))
NO_PAIRS = bool(os.environ.get('NO_PAIRS'))
MEGA_SETS = {}

OPP = {'North': 'South', 'South': 'North', 'East': 'West', 'West': 'East', 'Up': 'Down', 'Down': 'Up'}
LABELS = {
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


def all_doors(s):
    names = {x['name'] for x in s['doors']}
    return s['doors'] + [{'name': p, 'type': 'Normal', 'dir': 'South'} for p in s['portal_doors'] if p not in names]


FIXED = [('Hera Lobby Up Stairs', 'Hera Beetles Down Stairs'), ('Hera Startile Wide Up Stairs', 'Hera 4F Down Stairs'),
         ('Hera 4F Up Stairs', 'Hera 5F Down Stairs'), ('Hera 5F Up Stairs', 'Hera Boss Down Stairs')]


def pair_doors(chosen):
    doors = [(i, x) for i, p in chosen for x in all_doors(sectors[i]) if x['name'] != p]
    names = {x['name'] for _, x in doors}
    fixed = [(a, b) for a, b in FIXED if a in names and b in names]
    gone = {n for pr in fixed for n in pr}
    doors = [(i, x) for i, x in doors if x['name'] not in gone]
    rng.shuffle(doors)
    parent = {i: i for i, _ in chosen}

    def f(a):
        while parent[a] != a:
            a = parent[a]
        return a
    pairs, left = list(fixed), doors
    while left:
        opts = []
        for ai in range(len(left)):
            for bi in range(ai + 1, len(left)):
                (ia, a), (ib, b) = left[ai], left[bi]
                if ia != ib and a['type'] == b['type'] and OPP[a['dir']] == b['dir']:
                    opts.append(((f(ia) != f(ib), ia != ib), ai, bi))
        if not opts:
            # self-loop leftovers
            if SELF_LOOPS and all(x['type'] == 'SpiralStairs' for _, x in left):
                pairs.extend((x['name'], x['name']) for _, x in left)
                break
            raise Exception('unpairable')
        top = max(o[0] for o in opts)
        _, ai, bi = rng.choice([o for o in opts if o[0] == top])
        (ia, a), (ib, b) = left[ai], left[bi]
        parent[f(ia)] = f(ib)
        pairs.append((a['name'], b['name']))
        left = [x for k, x in enumerate(left) if k not in (ai, bi)]
    return pairs


ANCHOR = {'Turtle Rock': 'Turtle Rock Main', 'Desert Palace': 'Desert South', 'Skull Woods': 'Skull 2 East'}


def label_portals(dn, chosen, net):
    labels, passages = LABELS[dn]
    portals = [(i, p) for i, p in chosen if p]
    netp = [x for x in portals if x[0] in net]
    rng.shuffle(netp)
    out, remaining = {}, list(labels)
    for group in passages:
        lab = rng.choice([l for l in group if l in remaining])
        cand = next(x for x in netp if portal_info[x[1]]['passage'])
        out[lab] = cand[1]
        remaining.remove(lab)
        netp.remove(cand)
    anchor = ANCHOR.get(dn)
    if anchor and passages:
        # the overworld-reachable entrance must share the network with the ledge entrances
        if not netp:
            raise Exception('no network lobby for ' + anchor)
        out[anchor] = netp.pop(0)[1]
        remaining.remove(anchor)
    rest = netp + [x for x in portals if x[0] not in net]
    rng.shuffle(remaining)
    for lab, (i, p) in zip(remaining, rest):
        out[lab] = p
    return out


def portal_rooms(sol):
    return {r for i, p in sol['chosen'] if p for r in sectors[i]['rooms'][:1]}


order = sorted(sols, key=lambda dn: (min(len([s for s in sols[dn] if s['rooms'] == min(x['rooms'] for x in sols[dn])]), 30), rng.random()))
used, used_rooms = set(), set()
lobbies, doors, report = {}, {}, {}
DS_FIXED = []
if os.environ.get('DS_VANILLA'):
    lobbies.update({'Desert South': 'Desert Main Lobby S', 'Desert West': 'Desert West S',
                    'Desert East': 'Desert East Lobby S', 'Desert Back': 'Desert Back Lobby S',
                    'Skull 1': 'Skull 1 Lobby S', 'Skull 2 East': 'Skull 2 East Lobby SW',
                    'Skull 2 West': 'Skull 2 West Lobby S', 'Skull 3': 'Skull 3 Lobby SW'})
    fixed_regions = ['Desert Main Lobby', 'Desert West Lobby', 'Desert East Lobby', 'Desert Back Lobby', 'Desert Boss',
                     'Skull 1 Lobby', 'Skull 2 East Lobby', 'Skull 2 West Lobby', 'Skull 3 Lobby', 'Skull Boss',
                     'Skull Pinball', 'Skull Left Drop', 'Skull Pot Circle', 'Skull Back Drop']
    DS_FIXED = [i for i in range(len(sectors)) if i not in used and any(r in fixed_regions for r in sectors[i]['regions'])]
    used.update(DS_FIXED)
    used_rooms.update(r for i in DS_FIXED for r in sectors[i]['rooms'][:1])
for dn in order:
    ok = [s for s in sols[dn] if not used & set(s['idxs']) and not used_rooms & portal_rooms(s)]
    if not ok:
        raise SystemExit('no option left for ' + dn)
    rng.shuffle(ok)
    ok.sort(key=lambda s: s['rooms'])
    for sol in ok:
        try:
            pairs = pair_doors(sol['chosen'])
            labels = label_portals(dn, sol['chosen'], set(sol['net']))
            break
        except Exception:
            continue
    else:
        raise SystemExit('no pairable option for ' + dn)
    best = sol['rooms']
    used.update(sol['idxs'])
    used_rooms.update(portal_rooms(sol))
    lobbies.update(labels)
    MEGA_SETS[dn] = [next(r for r in sectors[i]['regions'] if not r.endswith(' Portal')) for i in sol['idxs']]
    if NO_PAIRS:
        pairs = []
    if dn in OPEN and pairs:
        loose = [pr for pr in pairs if pr not in FIXED]
        pairs.remove(rng.choice(loose))
    for a, b in pairs:
        doors[a] = b
    report[dn] = best
AX = {('Normal', 'North'): 0, ('Normal', 'South'): 0, ('Normal', 'East'): 1, ('Normal', 'West'): 1,
      ('SpiralStairs', 'Up'): 2, ('SpiralStairs', 'Down'): 2, ('Open', 'North'): 3, ('Open', 'South'): 3,
      ('Open', 'East'): 4, ('Open', 'West'): 4, ('StraightStairs', 'North'): 5, ('StraightStairs', 'South'): 5,
      ('Ladder', 'North'): 6, ('Ladder', 'South'): 6}
SIGN = {'North': 1, 'South': -1, 'East': 1, 'West': -1, 'Up': 1, 'Down': -1}
NO_CLUMP = {'Hyrule Dungeon Cellblock', 'Sanctuary', 'Hyrule Castle Throne Room', 'Sewers Rat Path', 'Tower Agahnim 1',
            'Skull Pinball', 'Skull Left Drop', 'Skull Pot Circle', 'Skull Back Drop', 'Swamp Lobby'}


_vc = {}
LOOPED = set()


def vec_of(i):
    if i in _vc:
        return _vc[i]
    v = [0] * 7
    for x in all_doors(sectors[i]):
        if x['name'] in lobbies.values() or x['name'] in LOOPED:
            continue
        v[AX[(x['type'], x['dir'])]] += SIGN[x['dir']]
    _vc[i] = tuple(v)
    return _vc[i]


def pick_castle_lobbies():
    # HC/AT lobbies from leftover rooms; in standard every HC lobby but South must be walk-through
    cand = [(i, pn) for i in range(len(sectors)) if i not in used for pn in sectors[i]['portal_doors']
            if not portal_info[pn]['deadEnd'] and portal_info[pn]['passage'] and not portal_info[pn]['std_restr']
            and not portal_info[pn]['lw_restr'] and not portal_info[pn]['bk_shuffle_req']
            and len(all_doors(sectors[i])) >= 2]
    rng.shuffle(cand)
    taken_rooms = set(used_rooms)
    out = {'Sanctuary': 'Sanctuary S'}
    for label in ['Hyrule Castle South', 'Hyrule Castle West', 'Hyrule Castle East', 'Agahnims Tower']:
        for i, pn in cand:
            room = sectors[i]['rooms'][:1]
            if room and room[0] in taken_rooms or pn in out.values():
                continue
            out[label] = pn
            taken_rooms.update(room)
            break
    return out


def clump(max_size, budget):
    # group leftover sectors into zero-sum clumps joined by a random spanning tree
    import itertools
    used_doors = set(doors) | set(doors.values()) | set(lobbies.values())
    pool = [i for i in range(len(sectors)) if i not in used and any(vec_of(i))]
    rng.shuffle(pool)
    free = set(pool)
    made = []
    for s in pool:
        if s not in free or len(made) >= budget:
            continue
        group = None
        for size in range(2, max_size + 1):
            others = [t for t in free if t != s]
            rng.shuffle(others)
            target = tuple(-x for x in vec_of(s))
            for combo in itertools.islice(itertools.combinations(others, size - 1), 30000):
                tot = tuple(sum(vec_of(c)[a] for c in combo) for a in range(7))
                if tot != target:
                    continue
                grp = [s] + list(combo)
                n_doors = sum(len([x for x in all_doors(sectors[i]) if x['name'] not in used_doors]) for i in grp)
                if n_doors - 2 * (len(grp) - 1) < 2:
                    continue
                group = grp
                break
            if group:
                break
        if not group:
            continue
        open_doors = {i: [x for x in all_doors(sectors[i]) if x['name'] not in used_doors] for i in group}
        linked, ok, new_pairs = [group[0]], True, []
        for t in group[1:]:
            opts = [(a, b) for a in open_doors[t] for li in linked for b in open_doors[li]
                    if a['type'] == b['type'] and OPP[a['dir']] == b['dir']]
            if not opts:
                ok = False
                break
            flat = [o for o in opts if o[0]['type'] != 'SpiralStairs']
            a, b = rng.choice(flat or opts)
            new_pairs.append((a['name'], b['name']))
            for i in group:
                open_doors[i] = [x for x in open_doors[i] if x['name'] not in (a['name'], b['name'])]
            linked.append(t)
        if not ok:
            continue
        for a, b in new_pairs:
            doors[a] = b
            used_doors.update((a, b))
        free.difference_update(group)
        made.append(group)
    return made, [i for i in free]


if os.environ.get('CASTLE_LOBBIES'):
    lobbies.update(pick_castle_lobbies())
if SELF_LOOPS and os.environ.get('CLUMP'):
    # self-loop surplus spiral stairs so the leftover pool balances on the stairs axis
    left = [i for i in range(len(sectors)) if i not in used]
    surplus = sum(vec_of(i)[2] for i in left + DS_FIXED)
    want = 'Up' if surplus > 0 else 'Down'
    taken = set(doors) | set(doors.values()) | set(lobbies.values())
    cands = [(i, x['name']) for i in left for x in all_doors(sectors[i])
             if x['type'] == 'SpiralStairs' and x['dir'] == want and x['name'] not in taken
             and len(all_doors(sectors[i])) >= 3]
    rng.shuffle(cands)
    for i, name in cands[:abs(surplus)]:
        doors[name] = name
        LOOPED.add(name)
    _vc.clear()
    report['stair_loops'] = min(abs(surplus), len(cands))
if os.environ.get('CLUMP'):
    mx, budget = (int(x) for x in os.environ['CLUMP'].split(','))
    made, rest = clump(mx, budget)
    report['clumps'] = len(made)
    report['unbalanced_left'] = len(rest)
    report['residual'] = [sum(vec_of(i)[a] for i in rest) for a in range(7)]
    if os.environ.get('SWEEP') and rest:
        # join every remaining unbalanced sector into one zero-sum clump
        used_doors = set(doors) | set(doors.values()) | set(lobbies.values())
        open_doors = {i: [x for x in all_doors(sectors[i]) if x['name'] not in used_doors] for i in rest}
        hub = max(rest, key=lambda i: len(open_doors[i]))
        linked = [hub]
        pending = [i for i in rest if i != hub]
        progress = True
        while pending and progress:
            progress = False
            for t in list(pending):
                opts = [(a, b) for a in open_doors[t] for li in linked for b in open_doors[li]
                        if a['type'] == b['type'] and OPP[a['dir']] == b['dir']]
                if not opts:
                    continue
                a, b = rng.choice(opts)
                doors[a['name']] = b['name']
                for i in rest:
                    open_doors[i] = [x for x in open_doors[i] if x['name'] not in (a['name'], b['name'])]
                linked.append(t)
                pending.remove(t)
                progress = True
        report['sweep_unlinked'] = len(pending)
base['doors'] = {1: {'lobbies': lobbies, 'doors': doors}}
yaml.safe_dump(base, open(sys.argv[5], 'w'), sort_keys=False)
if NO_PAIRS:
    json.dump(MEGA_SETS, open(sys.argv[5] + '.sets.json', 'w'))
print(json.dumps(report))
