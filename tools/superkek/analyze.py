import sys, os, json
sys.path.insert(0, os.getcwd())
import DoorShuffle, Main
orig = getattr(DoorShuffle, 'find_valid_combination', None)
def wrap(builder, *a, **k):
    try:
        return orig(builder, *a, **k)
    except Exception as e:
        regs = builder.master_sector.region_set() if builder.master_sector else []
        print(f'KEYFAIL {builder.name} key_doors_num={builder.key_doors_num} regions={len(regs)} {e}', flush=True)
        raise
DoorShuffle.find_valid_combination = wrap
orig_link = DoorShuffle.link_doors


def escape_check(world, player):
    # standard escape checkpoint: from the castle lobbies and Zelda's cell, Sanctuary must be out of reach without
    # crossing the throne room tapestry. Ignores item rules, so "ok" holds for any inventory.
    from collections import deque
    from BaseClasses import RegionType
    cut = {'Hyrule Castle Throne Room Tapestry', 'Hyrule Castle Tapestry Backwards'}
    starts = [p.door.entrance.parent_region for p in world.dungeon_portals[player]
              if p.name in ('Hyrule Castle South', 'Hyrule Castle West', 'Hyrule Castle East')]
    starts.append(world.get_region('Hyrule Dungeon Cellblock', player))
    sanc = world.get_region('Sanctuary', player)
    prev, q = {r: None for r in starts}, deque(starts)
    while q:
        r = q.popleft()
        for e in r.exits:
            c = e.connected_region
            if c is not None and c not in prev and e.name not in cut and c.type == RegionType.Dungeon:
                prev[c] = (r, e)
                q.append(c)
    if sanc not in prev:
        print(f'ESCAPE ok: Sanctuary only past the throne room '
              f'(Throne Room N <-> {world.get_door("Hyrule Castle Throne Room N", player).dest.name})', flush=True)
        return
    path, r = [], sanc
    while prev[r]:
        r, e = prev[r]
        path.append(e.name)
    print(f'ESCAPE BYPASS: Sanctuary reachable without the throne room: {" -> ".join(reversed(path))}', flush=True)


def patched(world, player):
    orig_link(world, player)
    if world.mode[player] == 'standard':
        escape_check(world, player)
    res = {}
    for name, b in world.dungeon_layouts[player].items():
        regs = b.master_sector.region_set() if b.master_sector else set()
        rooms = {d.roomIndex for d in world.doors if d.player == player and d.entrance and d.entrance.parent_region.name in regs and d.roomIndex >= 0}
        locs = [l.name for r in world.regions if r.player == player and r.name in regs for l in r.locations]
        res[name] = (len(rooms), len(regs), len(locs))
    for k, v in sorted(res.items(), key=lambda x: -x[1][0]):
        print(f'ROOMS {k:22s} supertiles={v[0]:3d} regions={v[1]:3d} locations={v[2]:3d}')
    if os.environ.get('LOCS_OUT'):
        by_d = {}
        for r in world.regions:
            if r.player == player and r.dungeon:
                by_d.setdefault(r.dungeon.name, []).extend(l.name for l in r.locations)
        json.dump(by_d, open(os.environ['LOCS_OUT'], 'w'))
        door_d = {d.name: d.entrance.parent_region.dungeon.name for d in world.doors
                  if d.player == player and d.entrance and d.entrance.parent_region.dungeon}
        json.dump(door_d, open(os.environ['LOCS_OUT'] + '.doors.json', 'w'))
    if os.environ.get('STOP'):
        raise SystemExit(0)
Main.link_doors = patched
DoorShuffle.link_doors = patched
sys.argv = ['DungeonRandomizer.py'] + sys.argv[1:]
import DungeonRandomizer
DungeonRandomizer.start()
