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
def patched(world, player):
    orig_link(world, player)
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
