import sys, os, json, random, yaml
sys.path.insert(0, os.getcwd())

# In-process mega dungeon builder. Runs DR up to dungeon assignment, then lays out Agahnims Tower and
# Hyrule Castle itself (traversal-aware, validated with DR's own explorer) and writes a full plando yaml.
# env: MEGA_OUT (yaml to write), MEGA_BASE (base yaml), AT_TARGET (supertiles), MEGA_SEED
import DoorShuffle
import source.dungeon.DungeonStitcher as DS
from BaseClasses import DoorType

OUT, BASE = os.environ['MEGA_OUT'], os.environ['MEGA_BASE']
AT_TARGET = int(os.environ.get('AT_TARGET', '40'))
rng = random.Random(int(os.environ.get('MEGA_SEED', '1')))
OPP = {'North': 'South', 'South': 'North', 'East': 'West', 'West': 'East', 'Up': 'Down', 'Down': 'Up'}
FIXED = [('Hera Lobby Key Stairs', 'Hera Tile Room Up Stairs'), ('Hera Lobby Down Stairs', 'Hera Basement Cage Up Stairs'),
         ('Hera Lobby Up Stairs', 'Hera Beetles Down Stairs'), ('Hera Startile Wide Up Stairs', 'Hera 4F Down Stairs'),
         ('Hera 4F Up Stairs', 'Hera 5F Down Stairs'), ('Hera 5F Up Stairs', 'Hera Boss Down Stairs')]
HC_ONLY = {'Hyrule Dungeon Cellblock', 'Sanctuary', 'Hyrule Castle Throne Room', 'Sewers Rat Path'}


def dname(door):
    return str(door.direction).split('.')[-1]


def compatible(a, b):
    return a.type == b.type and OPP[dname(a)] == dname(b)


def axis_vec(doors):
    v = {}
    for d in doors:
        if d.type == DoorType.SpiralStairs:
            continue
        axis = (d.type, dname(d) in ('North', 'South'))
        v[axis] = v.get(axis, 0) + (1 if dname(d) in ('North', 'East') else -1)
    return v


def balanced(sectors):
    tot = {}
    for s in sectors:
        for k, x in axis_vec(s.outstanding_doors).items():
            tot[k] = tot.get(k, 0) + x
    return all(x == 0 for x in tot.values()), tot


def rooms_of(sectors):
    return len({d.roomIndex for s in sectors for r in s.regions for e in r.exits if e.door for d in [e.door]
                if d.roomIndex >= 0})


DECOUPLED = bool(os.environ.get('DECOUPLED'))
# standard escape: Sanctuary only behind the throne room door, like DR's own Dungeon/Sewers split
# (split_dungeon_builder). HC_SPLIT=0 lays HC out as one piece (how the first published seeds were made).
HC_SPLIT = os.environ.get('HC_SPLIT', '1') != '0'
SEWERS_TARGET = int(os.environ.get('SEWERS_TARGET', '10'))
THRONE_N = 'Hyrule Castle Throne Room N'


def vec_add(t, v, sign):
    out = dict(t)
    for k, x in v.items():
        out[k] = out.get(k, 0) + sign * x
    return out


def split_hc(hc, dungeon_lobbies, lobby_doors, world, player):
    # -> (dungeon sectors, sewers sectors, link door): Throne Room N <-> link is the only way into the sewers half,
    # which holds Sanctuary; each half balances on its own once those two doors are set aside
    throne_n = world.get_door(THRONE_N, player)
    find = lambda reg: next(s for s in hc if any(r.name == reg for r in s.regions))
    sanc = find('Sanctuary')
    dungeon_must = {find('Hyrule Castle Throne Room'), find('Hyrule Dungeon Cellblock')}
    dungeon_must |= {s for s in hc if any(r in dungeon_lobbies for r in s.regions)}
    # the Swamp moat needs the overworld floodgate, which stays shut until Zelda reaches Sanctuary
    dungeon_must |= {s for s in hc if any(r.name in ('Swamp Lobby', 'Swamp Entrance') for r in s.regions)}
    if sanc in dungeon_must:
        return None
    # DR's choice of sewers access: a south door of a sector with somewhere else to go
    links = [(d, s) for s in hc if s not in dungeon_must for d in s.outstanding_doors
             if d.type == DoorType.Normal and dname(d) == 'South' and d not in lobby_doors and len(s.outstanding_doors) > 1]
    if not links:
        return None
    link, link_sec = rng.choice(links)
    vecs = {s: axis_vec([d for d in s.outstanding_doors if d not in (link, throne_n)]) for s in hc}
    musts = list(dict.fromkeys([sanc, link_sec]))
    pool = [s for s in hc if s not in dungeon_must and s not in musts]
    rng.shuffle(pool)
    sew = list(musts)
    for s in pool:
        if rooms_of(sew) >= SEWERS_TARGET:
            break
        sew.append(s)
    tot = {}
    for s in sew:
        tot = vec_add(tot, vecs[s], 1)
    l1 = lambda t: sum(abs(x) for x in t.values())
    for step in range(200):
        if l1(tot) == 0:
            break
        moves = [(l1(vec_add(tot, vecs[s], 1)), 'add', s) for s in pool if s not in sew]
        moves += [(l1(vec_add(tot, vecs[s], -1)), 'del', s) for s in sew if s not in musts]
        best = min(m[0] for m in moves)
        slack = 1 if best >= l1(tot) and rng.random() < 0.7 else 0
        best_moves = [m for m in moves if m[0] <= best + slack]
        _, kind, s = rng.choice(best_moves)
        if kind == 'add':
            sew.append(s)
        else:
            sew.remove(s)
        tot = vec_add(tot, vecs[s], 1 if kind == 'add' else -1)
    if l1(tot) != 0:
        return None
    return [s for s in hc if s not in sew], sew, link


def grow_split_hc(hc, entrance_names, lobby_region, lobby_doors, world, player):
    parts = split_hc(hc, [lobby_region[n] for n in ('Hyrule Castle South', 'Hyrule Castle West', 'Hyrule Castle East')],
                     lobby_doors, world, player)
    if not parts:
        return None, 0, None
    hc_d, hc_s, link = parts
    throne_n = world.get_door(THRONE_N, player)
    link_region = link.entrance.parent_region
    d_entr = [r for s in hc_d for r in s.regions if r.name in entrance_names] or [lobby_region['Hyrule Castle South']]
    s_entr = [link_region] + [r for s in hc_s for r in s.regions if r.name in entrance_names and r is not link_region]
    owner = {d: s for s in hc for d in s.outstanding_doors}
    owner[link].outstanding_doors.remove(link)
    owner[throne_n].outstanding_doors.remove(throne_n)
    try:
        d_prop, d_tries = grow('Hyrule Castle', hc_d, d_entr, world, player, path_name='Hyrule Castle Dungeon', tries=20)
        if not d_prop:
            return None, d_tries, None
        s_prop, s_tries = grow('Hyrule Castle', hc_s, s_entr, world, player, path_name='Hyrule Castle Sewers', tries=20,
                               extra_paths=[(link_region.name, 'Sanctuary')])
        if not s_prop:
            return None, d_tries + s_tries, None
    finally:
        owner[link].outstanding_doors.append(link)
        owner[throne_n].outstanding_doors.append(throne_n)
    prop = dict(d_prop)
    prop.update(s_prop)
    prop[throne_n], prop[link] = link, throne_n
    return prop, d_tries + s_tries, {'sewers_rooms': rooms_of(hc_s), 'sewers_sectors': len(hc_s), 'throne_link': link.name}


def grow_dec(name, sectors, entrance_regions, world, player, path_name=None, tries=60, extra_paths=()):
    # decoupled: each door's exit gets its own target; every door is used once as exit and once as entrance
    all_regions = set(r for s in sectors for r in s.regions)
    doors = [d for s in sectors for d in s.outstanding_doors]
    valid = {d.name: (d, i) for i, d in enumerate(doors)}
    sector_of = {d: s for s in sectors for d in s.outstanding_doors}
    bk_special = any(DS.check_for_special(s.regions) for s in sectors)
    paths = DS.determine_paths_for_dungeon(world, player, all_regions, path_name or name) + list(extra_paths)
    by_name = {d.name: d for d in doors}
    fixed = [(by_name[a], by_name[b]) for a, b in FIXED if a in by_name and b in by_name]
    for attempt in range(tries):
        prop, used_t = {}, set()
        for a, b in fixed:
            prop[a], prop[b] = b, a
            used_t.update((a, b))
        while True:
            st = DS.explore_proposal(name, entrance_regions, all_regions, prop, valid, bk_special, world, player)
            seen = set(st.visited_blue) | set(st.visited_orange)
            frontier = [d for d in doors if d not in prop and d.entrance.parent_region in seen]
            targets = [d for d in doors if d not in used_t and d.entrance.parent_region not in seen]
            if not targets:
                break
            fresh = [t for t in targets if not any(r in seen for r in sector_of[t].regions)]
            opts = [(f, t) for f in frontier for t in (fresh or targets) if compatible(f, t)]
            if not opts:
                opts = [(f, t) for f in frontier for t in targets if compatible(f, t)]
            if not opts:
                break
            f, t = rng.choice(opts)
            prop[f] = t
            used_t.add(t)
        srcs = [d for d in doors if d not in prop]
        tgts = [d for d in doors if d not in used_t]
        ok = False
        for _ in range(30):
            rng.shuffle(srcs)
            pool, trial, good = list(tgts), {}, True
            for a in srcs:
                m = [b for b in pool if compatible(a, b) and sector_of[b] is not sector_of[a]] or \
                    [b for b in pool if compatible(a, b) and b is not a]
                if m:
                    b = rng.choice(m)
                elif a.type == DoorType.SpiralStairs and a in pool:
                    b = a
                else:
                    good = False
                    break
                trial[a] = b
                pool.remove(b)
            if good:
                prop.update(trial)
                ok = True
                break
        if not ok:
            continue
        st = DS.explore_proposal(name, entrance_regions, all_regions, prop, valid, bk_special, world, player)
        if DS.check_valid(name, st, prop, valid, all_regions, paths, entrance_regions, bk_special, world, player):
            return prop, attempt
        if os.environ.get('MEGA_DEBUG') and attempt == tries - 1:
            seen = set(st.visited_blue) | set(st.visited_orange)
            print(f'DEBUG {name}: unreachable={sorted(r.name for r in all_regions - seen)}', flush=True)
    return None, tries


def grow(name, sectors, entrance_regions, world, player, path_name=None, tries=60, extra_paths=()):
    if DECOUPLED:
        return grow_dec(name, sectors, entrance_regions, world, player, path_name, tries, extra_paths)
    return grow_coupled(name, sectors, entrance_regions, world, player, path_name, tries, extra_paths)


def grow_coupled(name, sectors, entrance_regions, world, player, path_name=None, tries=60, extra_paths=()):
    all_regions = set(r for s in sectors for r in s.regions)
    doors = [d for s in sectors for d in s.outstanding_doors]
    valid = {d.name: (d, i) for i, d in enumerate(doors)}
    sector_of = {d: s for s in sectors for d in s.outstanding_doors}
    bk_special = any(DS.check_for_special(s.regions) for s in sectors)
    paths = DS.determine_paths_for_dungeon(world, player, all_regions, path_name or name) + list(extra_paths)
    by_name = {d.name: d for d in doors}
    fixed = [(by_name[a], by_name[b]) for a, b in FIXED if a in by_name and b in by_name]
    for attempt in range(tries):
        prop = {}
        for a, b in fixed:
            prop[a], prop[b] = b, a
        while True:
            st = DS.explore_proposal(name, entrance_regions, all_regions, prop, valid, bk_special, world, player)
            seen = set(st.visited_blue) | set(st.visited_orange)
            frontier = [d for d in doors if d not in prop and d.entrance.parent_region in seen]
            targets = [d for d in doors if d not in prop and d.entrance.parent_region not in seen]
            if not targets:
                break
            fresh = [t for t in targets if not any(r in seen for r in sector_of[t].regions)]
            opts = [(f, t) for f in frontier for t in (fresh or targets) if compatible(f, t)]
            if not opts:
                opts = [(f, t) for f in frontier for t in targets if compatible(f, t)]
            if not opts:
                break
            f, t = rng.choice(opts)
            prop[f], prop[t] = t, f
        left = [d for d in doors if d not in prop]
        rng.shuffle(left)
        ok = True
        while left:
            a = left.pop()
            m = [b for b in left if compatible(a, b) and sector_of[b] is not sector_of[a]] or \
                [b for b in left if compatible(a, b)]
            if m:
                b = rng.choice(m)
                left.remove(b)
                prop[a], prop[b] = b, a
            elif a.type == DoorType.SpiralStairs:
                prop[a] = a
            else:
                ok = False
                break
        if not ok:
            if os.environ.get('MEGA_DEBUG') and attempt == tries - 1:
                print(f'DEBUG {name}: unpairable leftovers {[d.name for d in left] + [a.name]}', flush=True)
            continue
        st = DS.explore_proposal(name, entrance_regions, all_regions, prop, valid, bk_special, world, player)
        if DS.check_valid(name, st, prop, valid, all_regions, paths, entrance_regions, bk_special, world, player):
            return prop, attempt
        if os.environ.get('MEGA_DEBUG') and attempt == tries - 1:
            seen = set(st.visited_blue) | set(st.visited_orange)
            print(f'DEBUG {name}: unreachable={sorted(r.name for r in all_regions - seen)} paths={paths}', flush=True)
    return None, tries


def patched(all_sectors, connections_tuple, world, player, *a, **k):
    portal = {p.name: p for p in world.dungeon_portals[player]}
    lobby_region = {n: p.door.entrance.parent_region for n, p in portal.items()}
    small = {}
    sets_file = os.environ.get('MEGA_SETS')
    if sets_file:
        for dn, regs in json.load(open(sets_file)).items():
            small[dn] = [next(s for s in all_sectors if any(r.name == reg for r in s.regions)) for reg in regs]
    if 'Tower of Hera' in small:
        for reg in ('Hera Tile Room', 'Hera Basement Cage'):
            s = next(s for s in all_sectors if any(r.name == reg for r in s.regions))
            if s not in small['Tower of Hera']:
                small['Tower of Hera'].append(s)
    taken = {s for v in small.values() for s in v}
    small_props = {}
    entrances_map = connections_tuple[0]

    def entrances_for(dn, secs, extra=()):
        regs = {r for s in secs for r in s.regions}
        names = set(entrances_map.get(dn, [])) | set(extra)
        return [r for r in regs if r.name in names]

    for dn, secs in small.items():
        ent = entrances_for(dn, secs)
        if not any(s.outstanding_doors for s in secs):
            continue
        prop, _ = grow(dn, secs, ent, world, player, tries=40)
        if not prop:
            print(f'MEGA SMALL FAILED {dn} entrances={[r.name for r in ent]} sectors={[s.regions[0].name for s in secs]}', flush=True)
            raise SystemExit(3)
        small_props[dn] = prop
    free = [s for s in all_sectors if s.outstanding_doors and s not in taken]
    find = lambda reg: next(s for s in free if any(r.name == reg for r in s.regions))
    at_boss = find('Tower Agahnim 1')
    at_lobby = next(s for s in free if lobby_region['Agahnims Tower'] in s.regions)
    hc_lobby_names = ['Hyrule Castle South', 'Hyrule Castle West', 'Hyrule Castle East', 'Sanctuary']
    hc_fixed = {s for s in free if any(r.name in HC_ONLY for r in s.regions)
                or any(lobby_region[n] in s.regions for n in hc_lobby_names)}
    # standard: the Swamp moat needs the overworld floodgate, so those rooms can't be in HC. Matched by region:
    # sector.item_logic is filled in DR's create_dungeon_builders, which this replaces, so it is empty here
    musts = [at_boss, at_lobby] + [s for s in free if s not in hc_fixed and (
        'Open Floodgate' in s.item_logic or any(r.name in ('Swamp Lobby', 'Swamp Entrance') for r in s.regions))]
    pool = [s for s in free if s not in hc_fixed and s not in musts]
    report = {}
    for attempt in range(int(os.environ.get('ASSIGN_TRIES', '400'))):
        rng.shuffle(pool)
        at = list(dict.fromkeys(musts))
        for s in pool:
            if rooms_of(at) >= AT_TARGET:
                break
            at.append(s)
        vecs = {s: axis_vec(s.outstanding_doors) for s in free}

        def l1(t):
            return sum(abs(x) for x in t.values())

        def add(t, v, sign):
            out = dict(t)
            for k2, x in v.items():
                out[k2] = out.get(k2, 0) + sign * x
            return out
        tot = {}
        for s in at:
            tot = add(tot, vecs[s], 1)
        locked = set(musts)
        for step in range(200):
            if l1(tot) == 0:
                break
            moves = [(l1(add(tot, vecs[s], 1)), 'add', s) for s in pool if s not in at]
            moves += [(l1(add(tot, vecs[s], -1)), 'del', s) for s in at if s not in locked]
            best = min(m2[0] for m2 in moves)
            if best >= l1(tot) and rng.random() < 0.7:
                best_moves = [m2 for m2 in moves if m2[0] <= best + 1]
            else:
                best_moves = [m2 for m2 in moves if m2[0] == best]
            _, kind, s = rng.choice(best_moves)
            if kind == 'add':
                at.append(s)
                tot = add(tot, vecs[s], 1)
            else:
                at.remove(s)
                tot = add(tot, vecs[s], -1)
        if l1(tot) != 0:
            if os.environ.get('MEGA_DEBUG'):
                print('DEBUG AT imbalance left', l1(tot), flush=True)
            continue
        hc = [s for s in free if s not in at]
        at_entr = [r for s in at for r in s.regions if r.name in set(entrances_map.get('Agahnims Tower', []))] or [lobby_region['Agahnims Tower']]
        if os.environ.get('MEGA_DEBUG'):
            print('DEBUG at_entr', [r.name for r in at_entr], 'hc_entr_names', entrances_map.get('Hyrule Castle'), 'at_names', entrances_map.get('Agahnims Tower'), flush=True)
        at_prop, at_tries = grow('Agahnims Tower', at, at_entr, world, player, tries=20)
        if not at_prop:
            continue
        split_info = {}
        if HC_SPLIT:
            hc_prop, hc_tries, split_info = grow_split_hc(hc, set(entrances_map.get('Hyrule Castle', [])), lobby_region,
                                                          {p.door for p in world.dungeon_portals[player] if p.door},
                                                          world, player)
        else:
            hc_entr = [r for s in hc for r in s.regions if r.name in set(entrances_map.get('Hyrule Castle', []))] or [lobby_region['Hyrule Castle South']]
            hc_prop, hc_tries = grow('Hyrule Castle', hc, hc_entr, world, player, path_name='Hyrule Castle Dungeon', tries=20)
        if not hc_prop:
            continue
        report = {'at_rooms': rooms_of(at), 'hc_rooms': rooms_of(hc), 'at_sectors': len(at), 'hc_sectors': len(hc),
                  'assign_attempt': attempt, 'at_tries': at_tries, 'hc_tries': hc_tries, **split_info}
        break
    else:
        print('MEGA FAILED', flush=True)
        raise SystemExit(2)
    base = yaml.safe_load(open(BASE))
    bd = base['doors'][1]['doors']
    done = set()
    small_type = os.environ.get('SMALL_TYPE', 'Bomb Door')
    keycap = json.load(open(os.environ['KEYCAP']))
    lobby_doors = {p.door for p in world.dungeon_portals[player] if p.door}

    def key_pairs(prop):
        seen_p, out = set(), []
        for a, b in prop.items():
            if a is b or a in seen_p or a in lobby_doors or b in lobby_doors or THRONE_N in (a.name, b.name):
                continue
            seen_p.update((a, b))
            if (a.type == DoorType.Normal and b.type == DoorType.Normal and a.name in keycap and b.name in keycap
                    and a.roomIndex != b.roomIndex):
                out.append(a)
        return out
    key_doors, nonkey_doors = set(), set()
    for label, prop in (('at', at_prop), ('hc', hc_prop)):
        cands = key_pairs(prop)
        rng.shuffle(cands)
        n = rng.randint(0, int(os.environ.get('MEGA_KEYS_MAX', '11')))
        key_doors.update(cands[:n])
        nonkey_doors.update(cands[n:])
        report[label + '_keys'] = min(n, len(cands))
    mega_regions = {r.name for s in at + hc for r in s.regions}
    report['mega_key_stairs'] = sorted(k for k, v in keycap.items() if v['type'] == 'SpiralStairs' and v['region'] in mega_regions)
    for kind, prop in [('mega', at_prop), ('mega', hc_prop)] + [('small', p) for p in small_props.values()]:
        for a, b in prop.items():
            if a in done and not DECOUPLED:
                continue
            if DECOUPLED:
                entry = {'dest': b.name, 'one-way': True}
                if (kind == 'small' and small_type and a is not b and a.type == DoorType.Normal
                        and b.type == DoorType.Normal and 0 <= a.doorListPos < 4 and 0 <= b.doorListPos < 4):
                    entry['type'] = small_type
                elif a in key_doors:
                    entry['type'] = 'Key Door'
                elif os.environ.get('FORCE_NONKEY') and a.name in keycap and 0 <= a.doorListPos < 4:
                    entry['type'] = small_type
                bd[a.name] = entry
                done.add(a)
                continue
            if (kind == 'small' and small_type and a is not b and a.type == DoorType.Normal and b.type == DoorType.Normal
                    and 0 <= a.doorListPos < 4 and 0 <= b.doorListPos < 4):
                bd[a.name] = {'dest': b.name, 'type': small_type}
            elif a in key_doors or b in key_doors:
                bd[a.name] = {'dest': b.name, 'type': 'Key Door'}
            elif os.environ.get('FORCE_NONKEY') and (a in nonkey_doors or b in nonkey_doors):
                bd[a.name] = {'dest': b.name, 'type': small_type}
            else:
                bd[a.name] = b.name
            done.update((a, b))
    # small dungeons: key-capable interior doors get a non-key type so no small key doors exist outside HC/AT
    small_regions = {r.name for dn, secs in small.items() if dn != 'Tower of Hera' for s in secs for r in s.regions}
    if os.environ.get('FORCE_NONKEY'):
        small_regions |= mega_regions
    interior_marked = 0
    for name, info in keycap.items():
        if info['type'] == 'Interior' and info['region'] in small_regions and not (isinstance(bd.get(name), dict) and 'type' in bd[name]):
            partner = world.get_door(name, player).dest
            pv = bd.get(partner.name) if partner is not None else None
            if isinstance(pv, dict) and 'type' in pv:
                continue
            bd[name] = {'type': small_type}
            interior_marked += 1
    report['interior_marked'] = interior_marked
    if 'Tower of Hera' in small and os.environ.get('HERA_KEYS'):
        # Hera keeps its two vanilla key doors; a lone key door trips the key analysis
        e = bd.get('Hera Lobby Key Stairs')
        bd['Hera Lobby Key Stairs'] = dict(e, type='Key Door') if isinstance(e, dict) else {'dest': e, 'type': 'Key Door'}
        bd['Hera Tridorm SE'] = {'type': 'Key Door'}
    yaml.safe_dump(base, open(OUT, 'w'), sort_keys=False)
    print('MEGA ' + json.dumps(report), flush=True)
    raise SystemExit(0)


DoorShuffle.create_dungeon_builders = patched
sys.argv = ['DungeonRandomizer.py'] + sys.argv[1:]
import DungeonRandomizer
DungeonRandomizer.start()
