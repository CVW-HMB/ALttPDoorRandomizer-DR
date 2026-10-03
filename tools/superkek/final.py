import sys, os, json, glob, re, subprocess, yaml
from concurrent.futures import ThreadPoolExecutor

# usage: final.py seed:name:pb ...   -> BPS + spoiler from two/mega_<seed>/pass2.yaml, verified
S = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get('DR_PY', sys.executable)
WT = os.path.abspath(os.path.join(S, '..', '..'))
env = dict(os.environ, LC_ALL='en_US.UTF-8', LANG='en_US.UTF-8', PYTHONPATH=f'{WT}/source')
PROG = ['Progressive Sword', 'Progressive Bow', 'Progressive Glove', 'Progressive Shield', 'Book of Mudora', 'Hammer',
        'Hookshot', 'Magic Mirror', 'Ocarina', 'Ocarina (Activated)', 'Pegasus Boots', 'Cape', 'Mushroom', 'Shovel',
        'Lamp', 'Magic Powder', 'Moon Pearl', 'Cane of Somaria', 'Cane of Byrna', 'Fire Rod', 'Ice Rod', 'Flippers',
        'Bombos', 'Ether', 'Quake', 'Blue Boomerang', 'Red Boomerang', 'Bug Catching Net', 'Magic Upgrade (1/2)',
        'Silver Arrows', 'Bottle', 'Bottle (Red Potion)', 'Bottle (Green Potion)', 'Bottle (Blue Potion)',
        'Bottle (Fairy)', 'Bottle (Bee)', 'Bottle (Good Bee)']


def one(spec):
    seed, name, pb = spec.split(':')
    seed, pb = int(seed), pb == 'pb'
    src = f'{S}/two/mega_{seed}/pass2.yaml'
    out = f"{S}/{os.environ.get('OUTDIR', 'final')}/{name}"
    os.makedirs(out, exist_ok=True)
    y = yaml.safe_load(open(src))
    y['settings'][1]['pseudoboots'] = pb
    y['settings'][1].update(json.loads(os.environ.get('EXTRA_SETTINGS', '{}')))
    yf = f'{out}/{name}.yaml'
    yaml.safe_dump(y, open(yf, 'w'), sort_keys=False)
    with open(f'{out}/log.txt', 'w') as f:
        subprocess.run([PY, f'{S}/analyze.py', '--customizer', yf, '--bps', '--spoiler', 'full', '--print_custom_yaml', *(['--skip_playthrough'] if os.environ.get('SKIP_PT') else []),
                        '--outputpath', out, '--seed', str(seed)], stdout=f, stderr=subprocess.STDOUT, cwd=WT,
                       env=dict(env, LOCS_OUT=f'{out}/locs.json'), timeout=1200)
    log = open(f'{out}/log.txt').read()
    if 'Total Time' not in log:
        errs = [l for l in log.splitlines() if re.search('Exception|Error', l)]
        return name, 'FAILED ' + (errs[-1] if errs else log[-200:])
    pass1 = json.load(open(f'{S}/two/mega_{seed}/locs.json'))
    now = json.load(open(f'{out}/locs.json'))
    same = {k: sorted(v) for k, v in pass1.items()} == {k: sorted(v) for k, v in now.items()}
    tset = set(now.get('Hyrule Castle', [])) | set(now.get('Agahnims Tower', []))
    placed = yaml.safe_load(open(glob.glob(f'{out}/*_custom.yaml')[0]))['placements'][1]
    hits = [(l, i) for l, i in placed.items() if i in PROG]
    inside = sum(1 for l, i in hits if l in tset)
    outside = [f'{i}@{l}' for l, i in hits if l not in tset]
    bps = glob.glob(f'{out}/*.bps')
    sizes = dict(re.findall(r'ROOMS (Hyrule Castle|Agahnims Tower)\s+supertiles=\s*(\d+)', log))
    bosses = dict(re.findall(r'^(Eastern Palace|Desert Palace|Tower of Hera|Palace of Darkness|Swamp Palace|Skull Woods|Thieves Town|Ice Palace|Misery Mire|Turtle Rock|Ganons Tower \w+): (.+)$', open(glob.glob(f'{out}/*Spoiler.txt')[0]).read(), re.M))
    return name, (f'ok bps={os.path.basename(bps[0]) if bps else None} layout_same={same} prog {inside}/{len(hits)} '
                  f'outside={outside} HC={sizes.get("Hyrule Castle")} AT={sizes.get("Agahnims Tower")} bosses={len(bosses)}')


with ThreadPoolExecutor(int(os.environ.get('PAR', '2'))) as ex:
    for name, res in ex.map(one, sys.argv[1:]):
        print(f'{name}: {res}', flush=True)
