# Super Kek Priest seed tools

Tools for rolling the two Super Kek Priest modes with this door randomizer:

- **Super Kek Priest**: standard mode, crossed doors, keysanity. Every dungeon except Hyrule Castle (HC) and
  Agahnims Tower (AT) is cut to the fewest rooms that still generate; HC (~115 supertiles) and AT (~45) take every
  other room. All progression is in HC/AT, the Triforce is in the Sanctuary chest, enemizer and full boss shuffle
  are on. Sanctuary is only reachable past the throne room door, as in a normal escape.
- **Super Kek Priest 64**: the same with decoupled doors (each door's exit leads somewhere independent of its
  entrance).

The full runbook (settings and why, every tuning knob, publishing, known failures) is
[INSTRUCTIONS.md](INSTRUCTIONS.md). This page gets you from a fresh clone to a verified seed.

## Setup (once)

You need Python 3.12 and a Japanese 1.0 ALttP ROM.

```bash
git clone -b tools/superkek-priest https://github.com/CVW-HMB/ALttPDoorRandomizer-DR.git
cd ALttPDoorRandomizer-DR
python3.12 -m venv .venv
.venv/bin/pip install -r resources/app/meta/manifests/pip_requirements.txt
cp /path/to/your/rom.sfc "Zelda no Densetsu - Kamigami no Triforce (Japan).sfc"
export LC_ALL=en_US.UTF-8   # DR crashes on startup without a UTF-8 locale
```

On Windows use `.venv\Scripts\python` instead of `.venv/bin/python`.

## Try a ready-made seed first

[examples/](examples/) has two complete customizer files from the pipeline: every door, lobby and progression
preference already decided. Rolling one with its seed number gives the same patch every time.

```bash
# Super Kek Priest, pseudo boots (about 3 minutes)
.venv/bin/python DungeonRandomizer.py --customizer tools/superkek/examples/super_kek_priest_pb_7002.yaml \
  --seed 7002 --bps --spoiler full --outputpath out/example

# Super Kek Priest 64, pseudo boots (under a minute; decoupled seeds skip the spoiler playthrough)
.venv/bin/python DungeonRandomizer.py --customizer tools/superkek/examples/super_kek_priest_64_pb_8001.yaml \
  --seed 8001 --bps --spoiler full --skip_playthrough --outputpath out/example64
```

The `.bps` in the output folder patches your ROM (for example with the online patcher at
alttprpatch.synack.live).

## Roll new seeds

Run these from `tools/superkek/`. Seed numbers are your choice; each one gives a different layout. Use numbers
you have not published before.

### Super Kek Priest (coupled)

```bash
cd tools/superkek
PY=../../.venv/bin/python
export EXTRA_SETTINGS='{"shuffleenemies": "shuffled", "any_enemy_logic": "none", "shufflebosses": "full", "dungeon_counters": "on", "collection_rate": true}'

# 1. build and roll 8 candidate layouts, 2 at a time (about 2 minutes per pair)
ROLL_TMO=150 PAR=2 $PY megarun.py 1000 8
#    1000: ROLLED | AT=45 HC=119 keys AT=7 HC=11 sewers=14 via TR Lava Escape SE | build 2s roll 70s

# 2. place progression in HC/AT, for the seeds that printed ROLLED
PAR=2 $PY twopass.py mega 1000,1001
#    seed 1000: layout identical=True; ok: 38/38 progression items in HC/AT ...

# 3. build the patches: seed:name:plain or seed:name:pb (pseudo boots)
OUTDIR=final PAR=2 $PY final.py 1000:my_seed_1:plain 1001:my_seed_2:pb
#    my_seed_1: ok bps=... escape=ok layout_same=True prog 38/39 outside=["Hammer@Link's Uncle"] ...

# 4. check before you share
$PY verify.py final/my_seed_1 final/my_seed_2
```

### Super Kek Priest 64 (decoupled)

```bash
cd tools/superkek
PY=../../.venv/bin/python
unset EXTRA_SETTINGS   # the decoupled base file already has every setting

DECOUPLED=1 MEGA_KEYS_MAX=0 SKIP_PT=1 ROLL_TMO=150 BASE_YAML=$PWD/base_decoupled.yaml PAR=2 $PY megarun.py 2000 6
SKIP_PT=1 PAR=2 TMO=200 $PY twopass.py mega 2000,2001
SKIP_PT=1 OUTDIR=final_dec PAR=2 $PY final.py 2000:my_64_seed_1:pb 2001:my_64_seed_2:pb
$PY verify.py final_dec/my_64_seed_1 final_dec/my_64_seed_2
```

Keep `PAR` at 2 or 3: each process is a full randomizer run, and more than that overheats a laptop.

## Which seeds are good

About 3 in 4 candidates roll. The rest print why they failed (`roll timeout`, `roll failed: ...`,
`escape bypass`, `pick failed`), and you simply skip them. Share a seed only when:

- `final.py` printed `ok`, `escape=ok` and `layout_same=True`, and the only progression item outside HC/AT is the one
  on Link's Uncle;
- `verify.py` shows the hash, `Small Key shuffle: wild`, `Big Key shuffle: Yes`, `Sanctuary chest: Triforce` and
  `money spawned: none`. It prints `ROLL FAILED ... do not publish` for a folder whose roll did not finish.

If `final.py` fails on a seed that passed step 2 (rare: an enemizer error in DR's spoiler playthrough), it deletes
that patch; pick another seed.

Everything you need to keep is in the `final*/<name>/` folder: the `.bps`, the spoiler, the exact customizer file
(`<name>.yaml`) and `DR_<seed>_custom.yaml` with every placement. The seed number plus `<name>.yaml` reproduces the
patch exactly, so keep seed numbers private while a seed is live.

## Files

| File | What it is |
|---|---|
| `base_coupled.yaml`, `base_decoupled.yaml` | The mode settings every roll starts from (customizer format) |
| `examples/*.yaml` | Complete customizer files produced by the pipeline, ready to roll |
| `megarun.py` | Picks room sets, builds the HC/AT layout (`megagen.py`) and test-rolls it |
| `twopass.py` | Rolls twice: finds HC/AT locations, then prefers progression there |
| `final.py` | Builds the `.bps` and spoiler with the final settings, re-checks layout and progression |
| `verify.py` | Applies the patch and prints hash, settings, counts and the money check |
| `analyze.py` | Wrapper used by the others; prints room counts and the escape check on every roll |
| `pick.py`, `megagen.py` | Room set and layout builders |
| `sectors.json`, `keycap.json`, `solutions.json` | Precomputed door data (see INSTRUCTIONS.md to regenerate) |

Work folders (`mega/`, `two/`, `final*/`, `out/`) are gitignored.
