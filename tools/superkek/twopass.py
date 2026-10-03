import sys, os, json, glob, re, subprocess, yaml
from concurrent.futures import ThreadPoolExecutor

# usage: twopass.py tag seed[,seed...]   (pass-1 layouts come from rand/<tag>/r<seed>.yaml)
S = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get('DR_PY', sys.executable)
WT = os.environ.get('WT', os.path.abspath(os.path.join(S, '..', '..')))
env = dict(os.environ, LC_ALL='en_US.UTF-8', LANG='en_US.UTF-8', PYTHONPATH=f'{WT}/source')
TMO = int(os.environ.get('TMO', '600'))
tag, seeds = sys.argv[1], [int(x) for x in sys.argv[2].split(',')]

PROGRESSION = ['Progressive Sword', 'Progressive Bow', 'Progressive Glove', 'Progressive Shield', 'Book of Mudora',
               'Hammer', 'Hookshot', 'Magic Mirror', 'Ocarina', 'Ocarina (Activated)', 'Pegasus Boots', 'Cape',
               'Mushroom', 'Shovel', 'Lamp', 'Magic Powder', 'Moon Pearl', 'Cane of Somaria', 'Cane of Byrna',
               'Fire Rod', 'Ice Rod', 'Flippers', 'Bombos', 'Ether', 'Quake', 'Blue Boomerang', 'Red Boomerang',
               'Bug Catching Net', 'Magic Upgrade (1/2)', 'Silver Arrows', 'Bottle', 'Bottle (Red Potion)',
               'Bottle (Green Potion)', 'Bottle (Blue Potion)', 'Bottle (Fairy)', 'Bottle (Bee)', 'Bottle (Good Bee)']
TARGET = ['Hyrule Castle', 'Agahnims Tower']


def run(args, log, extra_env=None):
    with open(log, 'w') as f:
        try:
            subprocess.run([PY, f'{S}/analyze.py'] + args, stdout=f, stderr=subprocess.STDOUT, cwd=WT,
                           env=dict(env, **(extra_env or {})), timeout=TMO)
        except subprocess.TimeoutExpired:
            return False
    return 'Total Time' in open(log).read()


def one(seed):
    out = f'{S}/two/{tag}_{seed}'
    os.makedirs(out, exist_ok=True)
    src = os.environ.get('SRC_FMT', f'{S}/mega/full{{seed}}.yaml').format(seed=seed)
    locs_file = f'{out}/locs.json'
    if not run(['--customizer', src, '--suppress_rom', '--spoiler', 'none', '--print_custom_yaml', *(['--skip_playthrough'] if os.environ.get('SKIP_PT') else []),
                '--outputpath', out, '--seed', str(seed)], f'{out}/pass1.log', {'LOCS_OUT': locs_file}):
        return seed, 'pass1 failed'
    exported = glob.glob(f'{out}/*_custom.yaml')[0]
    by_d = json.load(open(locs_file))
    import random
    rng = random.Random(seed)
    targets = []
    for d in TARGET:
        cand = sorted(l for l in set(by_d.get(d, [])) - {'Sanctuary'}
                      if 'Key Drop' not in l and 'Pot Key' not in l and 'Big Key' not in l)
        rng.shuffle(cand)
        targets.extend(cand[:len(by_d.get(d, [])) // 2])
    rng.shuffle(targets)
    pool = yaml.safe_load(open(exported)).get('item_pool', {}).get(1, {})
    items = [i for i in PROGRESSION if pool.get(i) or i.startswith('Bottle')]
    custom = yaml.safe_load(open(src))
    want = int(os.environ.get('RESERVE_MULT', '2')) * sum(pool.get(i, 0) for i in items)
    targets = sorted(targets[:want])
    custom['advanced_placements'] = {1: [{'type': 'PreferredLocationGroup', 'items': items, 'locations': targets}]}
    p2 = f'{out}/pass2.yaml'
    yaml.safe_dump(custom, open(p2, 'w'), sort_keys=False)
    out2 = f'{out}/p2'
    os.makedirs(out2, exist_ok=True)
    if not run(['--customizer', p2, '--suppress_rom', '--spoiler', 'full', '--print_custom_yaml', *(['--skip_playthrough'] if os.environ.get('SKIP_PT') else []), '--outputpath', out2,
                '--seed', str(seed)],
               f'{out}/pass2.log', {'LOCS_OUT': f'{out}/locs2.json'}):
        txt = open(f'{out}/pass2.log').read()
        errs = [l for l in txt.splitlines() if re.search('Exception|Error', l)]
        return seed, 'pass2 failed: ' + (errs[-1][:150] if errs else 'timeout')
    # where did progression land?
    by_d2 = json.load(open(f'{out}/locs2.json'))
    same = {k: sorted(v) for k, v in by_d.items()} == {k: sorted(v) for k, v in by_d2.items()}
    tset = {l for d in TARGET for l in by_d2.get(d, [])}
    final = yaml.safe_load(open(glob.glob(f'{out2}/*_custom.yaml')[0]))['placements'][1]
    total_items = sum(pool.get(i, 0) for i in items)
    hits = [(loc, it) for loc, it in final.items() if it in items]
    placed = len(hits)
    inside = sum(1 for loc, it in hits if loc in tset)
    outside = [f'{it}@{loc}' for loc, it in hits if loc not in tset]
    json.dump(outside, open(f'{out}/outside.json', 'w'), indent=1)
    return seed, f'layout identical={same}; ok: {inside}/{placed} progression items in HC/AT ({len(targets)} target locations, pool {total_items})'


with ThreadPoolExecutor(int(os.environ.get('PAR', '4'))) as ex:
    for seed, res in ex.map(one, seeds):
        print(f'seed {seed}: {res}', flush=True)
