import sys, json, os
sys.path.insert(0, os.getcwd())
import DoorShuffle
try:
    from DungeonGenerator import dungeon_boss_sectors, define_sector_features
except ImportError:
    from source.dungeon.DungeonGenerationCommon import dungeon_boss_sectors, define_sector_features
out = {}
orig = DoorShuffle.create_dungeon_builders
def patched(all_sectors, connections_tuple, world, player, pool, *a, **k):
    secs = []
    for s in all_sectors:
        define_sector_features([s])
        secs.append({
            'regions': [r.name for r in s.regions],
            'doors': [{'name': d.name, 'dir': str(d.direction).split('.')[-1], 'type': str(d.type).split('.')[-1],
                       'portalAble': d.portalAble, 'deadEnd': d.deadEnd, 'passage': d.passage,
                       'std_restr': d.standard_restricted, 'lw_restr': d.lw_restricted} for d in s.outstanding_doors],
            'chests': s.chest_locations,
            'locs': [l.name for r in s.regions for l in r.locations],
            'c_switch': bool(s.c_switch), 'blue_barrier': bool(s.blue_barrier),
            'item_logic': sorted(s.item_logic) if s.item_logic else [],
            'portal_doors': [d.name for d in world.doors if d.player == player and d.portalAble and d.entrance.parent_region in s.regions],
            'rooms': sorted({d.roomIndex for d in world.doors if d.player == player and d.entrance and d.entrance.parent_region in s.regions and d.roomIndex >= 0}),
            'boss': any(r.name in sum(dungeon_boss_sectors.values(), []) for r in s.regions),
        })
    portals = []
    for d in world.doors:
        if d.player == player and d.portalAble:
            portals.append({'name': d.name, 'region': d.entrance.parent_region.name, 'deadEnd': d.deadEnd,
                            'passage': d.passage, 'std_restr': d.standard_restricted, 'lw_restr': d.lw_restricted,
                            'bk_shuffle_req': d.bk_shuffle_req, 'dir': str(d.direction).split('.')[-1]})
    portal_flags = {p.name: dict(dest=p.destination, deadEnd=p.deadEnd, lw=p.light_world) for p in world.dungeon_portals[player]}
    inacc = sorted(world.inaccessible_regions[player])
    portal_assign = {p.name: (p.door.name if p.door else None) for p in world.dungeon_portals[player]}
    json.dump({'sectors': secs, 'portals': portals, 'portal_assign': portal_assign, 'portal_flags': portal_flags, 'inacc': inacc,
               'entrances_map': {k: list(v) for k, v in connections_tuple[0].items()}},
              open(os.environ['DUMP_OUT'], 'w'), indent=1)
    raise SystemExit('dumped')
DoorShuffle.create_dungeon_builders = patched
sys.argv = ['DungeonRandomizer.py'] + sys.argv[1:]
import DungeonRandomizer
DungeonRandomizer.start()
