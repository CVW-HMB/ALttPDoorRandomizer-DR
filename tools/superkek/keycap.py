import sys, os, json
sys.path.insert(0, os.getcwd())
import DoorShuffle
from BaseClasses import DoorType
from RoomData import DoorKind


def patched(all_sectors, connections_tuple, world, player, *a, **k):
    out = {}
    for d in world.doors:
        if d.player != player or not (0 <= d.doorListPos < 4) or d.roomIndex < 0:
            continue
        room = world.get_room(d.roomIndex, player)
        pos, kind = room.doorList[d.doorListPos]
        if d.type == DoorType.Interior:
            cap = kind in DoorShuffle.okay_interiors
        elif d.type == DoorType.SpiralStairs:
            cap = kind in [DoorKind.StairKey, DoorKind.StairKey2, DoorKind.StairKeyLow]
        elif d.type == DoorType.Normal:
            cap = kind in DoorShuffle.okay_normals
        else:
            cap = False
        if cap:
            out[d.name] = {'type': str(d.type).split('.')[-1], 'region': d.entrance.parent_region.name}
    json.dump(out, open(os.environ['KEYCAP_OUT'], 'w'), indent=1)
    raise SystemExit(0)


DoorShuffle.create_dungeon_builders = patched
sys.argv = ['DungeonRandomizer.py'] + sys.argv[1:]
import DungeonRandomizer
DungeonRandomizer.start()
