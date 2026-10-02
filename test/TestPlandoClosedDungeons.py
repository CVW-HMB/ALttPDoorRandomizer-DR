import unittest
from collections import defaultdict
from types import SimpleNamespace

from DoorShuffle import (default_door_connections, default_one_way_connections, find_valid_bd_combination, ladders,
                         open_edges, spiral_staircases, straight_staircases)
from source.classes.CustomSettings import CustomSettings
from test.TestBase import build_vanilla_world


def desert_pairs():
    pairs = {}
    tables = (default_door_connections, default_one_way_connections, spiral_staircases, straight_staircases,
              open_edges, ladders)
    for table in tables:
        for a, b in table:
            if a.startswith('Desert') and b.startswith('Desert'):
                pairs[a] = b
    return pairs


def customizer(doors):
    settings = CustomSettings()
    settings.file_source = {'doors': {1: {'doors': doors}}}
    return settings


class TestClosedSplitDungeon(unittest.TestCase):
    # every Desert door plando'd leaves no door for the generator, so Desert is never split into Main and Back
    def test_fully_plandoed_desert_keeps_its_name(self):
        world = build_vanilla_world(customizer=customizer(desert_pairs()), door_shuffle='basic')
        self.assertIn('Desert Palace', world.dungeon_layouts[1])
        self.assertIn('Desert Palace', world.key_logic[1])


def door(name):
    return SimpleNamespace(name=name)


class TestForcedBombDoors(unittest.TestCase):
    # more plando'd bomb doors than the generator suggested used to request a negative sample
    def test_custom_bomb_doors_beyond_suggestion(self):
        custom = [(door('A'), door('B')), (door('C'), door('D'))]
        types = {'Bomb Door': defaultdict(list), 'Dash Door': defaultdict(list)}
        types['Bomb Door']['Test'] = list(custom)
        world = SimpleNamespace(custom_door_types={1: types})
        builder = SimpleNamespace(name='Test', candidates=SimpleNamespace(bomb_dash=list(custom)))
        bombs, dashes, _ = find_valid_bd_combination(builder, (0, 0), world, 1)
        self.assertEqual(bombs, custom)
        self.assertEqual(dashes, [])


if __name__ == '__main__':
    unittest.main()
