import sys, json, os
sys.argv = [sys.argv[0], sys.argv[1]] + sys.argv[2:]
import solve
from solve import sectors, spec, solve as solve_dn

avoid_names = set(json.loads(os.environ.get('AVOID', '[]')))
avoid = {i for i, s in enumerate(sectors) if any(r in avoid_names for r in s['regions'])}
mx = {'Turtle Rock': 3, 'Desert Palace': 3}
out = {}
skip = set(json.loads(os.environ.get('SKIP', '[]')))
for dn in [x for x in spec if x not in skip]:
    sols = solve_dn(dn, avoid, max_extra=mx.get(dn, 2), want=100000)
    best = min(solve.rooms_of(s[0]) for s in sols)
    slack = 0 if dn in mx else 1
    keep = [s for s in sols if solve.rooms_of(s[0]) <= best + slack]
    sets = [frozenset(s[0]) for s in keep]
    keep = [s for s, a in zip(keep, sets) if not any(b < a for b in sets)]
    out[dn] = [{'idxs': s[0], 'chosen': [[i, p] for i, p, v in s[1]], 'net': s[2][1], 'rooms': solve.rooms_of(s[0])} for s in keep]
    print(dn, 'min supertiles', best, 'solutions', len(keep), flush=True)
json.dump(out, open(sys.argv[2], 'w'))
