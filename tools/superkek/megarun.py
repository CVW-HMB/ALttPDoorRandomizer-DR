import sys, os, re, json, time, subprocess
from concurrent.futures import ThreadPoolExecutor

# usage: megarun.py first_seed count  -> pick + build + roll each world, logging everything
S = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get('DR_PY', sys.executable)
WT = os.path.abspath(os.path.join(S, '..', '..'))
AT_TARGET = os.environ.get('AT_TARGET', '40')
env = dict(os.environ, LC_ALL='en_US.UTF-8', LANG='en_US.UTF-8', PYTHONPATH=f'{WT}/source')
first, count = int(sys.argv[1]), int(sys.argv[2])
os.makedirs(f'{S}/mega', exist_ok=True)


def one(s):
    t0 = time.time()
    base = f'{S}/mega/base{s}.yaml'
    full = f'{S}/mega/full{s}.yaml'
    p = subprocess.run([PY, f'{S}/pick.py', f'{S}/sectors.json', os.environ.get('SOLS', f'{S}/solutions.json'), os.environ.get('BASE_YAML', f'{S}/base_coupled.yaml'),
                        str(s), base], capture_output=True, text=True,
                       env=dict(env, SELF_LOOPS='1', CASTLE_LOBBIES='1', NO_PAIRS='1'))
    if p.returncode:
        return s, 'pick failed', None, time.time() - t0, None
    with open(f'{S}/mega/build{s}.log', 'w') as f:
        try:
            subprocess.run([PY, f'{S}/megagen.py', '--customizer', base, '--suppress_rom', '--spoiler', 'none',
                            '--outputpath', f'{S}/out/mega{s}', '--seed', str(s)], stdout=f, stderr=subprocess.STDOUT,
                           cwd=WT, timeout=900,
                           env=dict(env, MEGA_OUT=full, MEGA_BASE=base, MEGA_SETS=base + '.sets.json',
                                    KEYCAP=f'{S}/keycap.json', AT_TARGET=AT_TARGET, MEGA_SEED=str(s)))
        except subprocess.TimeoutExpired:
            return s, 'build timeout', None, time.time() - t0, None
    blog = open(f'{S}/mega/build{s}.log').read()
    m = re.search(r'^MEGA (\{.*\})$', blog, re.M)
    if not m:
        tail = [l for l in blog.splitlines() if re.search('MEGA|Error|Exception|Killed', l)]
        return s, 'build failed: ' + (tail[-1][:120] if tail else blog[-120:]), None, time.time() - t0, None
    info = json.loads(m.group(1))
    tb = time.time() - t0
    out = f'{S}/mega/roll{s}'
    os.makedirs(out, exist_ok=True)
    with open(f'{out}/log.txt', 'w') as f:
        try:
            subprocess.run([PY, f'{S}/analyze.py', '--customizer', full, '--suppress_rom', '--spoiler', 'full',
                            '--print_custom_yaml', *(['--skip_playthrough'] if os.environ.get('SKIP_PT') else []), '--outputpath', out, '--seed', str(s)], stdout=f,
                           stderr=subprocess.STDOUT, cwd=WT, timeout=int(os.environ.get("ROLL_TMO", "900")), env=dict(env, LOCS_OUT=f'{out}/locs.json'))
        except subprocess.TimeoutExpired:
            return s, 'roll timeout', info, tb, time.time() - t0 - tb
    rlog = open(f'{out}/log.txt').read()
    tr = time.time() - t0 - tb
    if 'Total Time' in rlog:
        return s, 'ROLLED', info, tb, tr
    errs = [l for l in rlog.splitlines() if re.search(r'KEYFAIL|Exception|Error', l)]
    return s, 'roll failed: ' + (errs[-1][:140] if errs else rlog[-140:]), info, tb, tr


with ThreadPoolExecutor(int(os.environ.get('PAR', '4'))) as ex:
    for s, res, info, tb, tr in ex.map(one, range(first, first + count)):
        size = f"AT={info['at_rooms']} HC={info['hc_rooms']} keys AT={info['at_keys']} HC={info['hc_keys']}" if info else ''
        print(f'{s}: {res} | {size} | build {tb:.0f}s' + (f' roll {tr:.0f}s' if tr else ''), flush=True)
