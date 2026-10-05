# Super Kek Priest: rolling HC/AT mega dungeon seeds

Everything needed to roll, verify, publish and list these seeds again, written so a fresh session needs nothing else.
Built in one long session on 2026-10-02. Branch: `tools/superkek-priest` on `CVW-HMB/ALttPDoorRandomizer-DR`
(cut from `fix/closed-split-dungeon-and-forced-bd-doors`, PR #13, which the tools depend on).

## The modes

**Super Kek Priest**: every dungeon except Hyrule Castle (HC) and Agahnims Tower (AT, a.k.a. Castle Tower) is cut to
the fewest rooms that still generate; HC and AT absorb every other supertile (HC ~115, AT ~45; normal crossed is
HC 18 / AT 11; the game has ~184 supertiles). All progression is preferred into HC/AT. Triforce is in the
Sanctuary chest (game ends when you open it).

**Super Kek Priest 64**: the same with decoupled doors (every door's exit leads somewhere independent of its entrance).

### Settings

| Setting | Super Kek Priest | Super Kek Priest 64 |
|---|---|---|
| mode | standard (random Uncle weapon is DR's default in standard) | same |
| door_shuffle / intensity | crossed / 3 | same |
| pottery | lottery (every pot is a location) | same |
| dropshuffle | keys | same |
| mapshuffle, compassshuffle | true | same |
| keyshuffle / bigkeyshuffle | wild / true (keysanity: small and big keys anywhere) | same |
| door_self_loops | true | same |
| shuffleenemies | shuffled | same |
| any_enemy_logic | none ("enemies have logical implication: off", GUI "Forbid special enemies") | same |
| shufflebosses | full | same |
| dungeon_counters | on (always show dungeon item + key counts) | same |
| collection_rate | true (total world count) | same |
| pseudoboots | half the seeds | all |
| decoupledoors | false | **true** |
| key_logic_algorithm | partial (default) | **strict** (partial's exhaustive analysis takes 7+ min on one-way mega dungeons) |
| trap_door_mode | optional (default) | **oneway** (DR trap code assumes two-way doors) |
| standardize_palettes | standardize (default) | **original** (DR palette code assumes two-way doors) |
| placements | `Sanctuary: Triforce` | same |
| item_pool_adjust | `Triforce: 1`, `Rupees (20): -1` | same |

`base_coupled.yaml` has the coupled base (enemizer/bosses/counters come from `EXTRA_SETTINGS` in the two-pass and
final steps, see below).
`base_decoupled.yaml` has every 64 setting, used from the first step.

### What each dungeon ends up as

- HC / AT: mega dungeons, laid out by our code (not DR's generator). AT is sized by `AT_TARGET` (default 40, lands
  34-55 after balancing); HC gets every room left over (112-132 supertiles, 420-500 item locations).
- Small dungeons at their minimum: Eastern/PoD/Swamp/Mire/GT/Ice 2 supertiles, Thieves 3, Desert 4, TR 4, Hera 5-6,
  Skull 6. Floors come from: one lobby per overworld entrance (Desert/TR/Skull have 4, HC 4 incl. Sanctuary),
  Skull's 4 drop-down rooms, Hera's tower being one sector (fused by drops), Blind's cell in Thieves.
- Small keys: HC/AT 11 key doors each (DR's hard cap `max_computation = 11` in `shuffle_small_key_doors`),
  Hera 2 (its vanilla key stairs cannot be typed away), every other dungeon 0.

## Environment

- Repo checkout with this branch, plus `Zelda no Densetsu - Kamigami no Triforce (Japan).sfc` (JP 1.0) at the repo root.
- Python 3.12 venv at the repo root (`.venv`), from DR's own manifest; setup commands are in `README.md` next to
  this file. The scripts launch sub-processes with the same interpreter (override with `DR_PY`).
- `LC_ALL=en_US.UTF-8` is required or DR crashes in `BabelFish` (`locale.getdefaultlocale()` returns None). The
  scripts set it for their sub-processes; set it yourself for one-off DR runs.
- DR imports need `PYTHONPATH=<repo>/source` (scripts set it).
- Run everything from `tools/superkek/` with the venv python. Work output goes to `mega/`, `two/`, `final*/`
  (gitignored).
- Keep parallelism at 2-3 (`PAR`); 8 parallel DR processes overheat the laptop and get killed silently.

## Pipeline

```
pick.py      choose each small dungeon's room set + lobbies (random among minimal solutions), HC/AT lobbies
megagen.py   runs DR up to dungeon assignment, then lays out every dungeon itself:
             small dungeons wired from their room set, AT = random balanced room set of ~AT_TARGET supertiles,
             HC = every remaining room; each grown outward from its lobby using DR's own explorer
             (DungeonStitcher.explore_proposal / check_valid) so one-way ledges, drops and crystal state are
             respected; writes a full door plando (mega/full<seed>.yaml). HC is two halves joined only by the
             throne room door (see "Escape checkpoint" below)
megarun.py   pick -> megagen -> one DR roll of the plando (validates it), PAR at a time
twopass.py   pass 1 re-rolls the plando and dumps HC/AT locations; pass 2 adds a PreferredLocationGroup that puts
             every progression item in HC/AT (layout is identical in both passes, checked)
final.py     builds the BPS from pass 2 with the per-seed settings, re-checks layout + progression
verify.py    patch applies, ROM hash in alttprasyncs icon names, settings, HUD bytes, per-dungeon counts
```

Data files (regenerate only if DR's door data changes):

- `sectors.json`: every sector (room group) with outstanding doors, lobby-capable doors, locations, rooms.
  From `dump.py` (hooks `create_dungeon_builders`).
- `keycap.json`: every key-capable door (DR's own rule: Normal door in slot 0-3 with a key-capable kind on both
  sides, Interior in `okay_interiors`, SpiralStairs with a StairKey kind). From `keycap.py`.
- `solutions.json`: every minimal room set per small dungeon (`solve.py` + `precompute.py`), filtered by
  `build_solutions.py`. The committed file is the exact one the published seeds used.

Regenerate (only when needed):

```bash
cd <repo>
export LC_ALL=en_US.UTF-8 PYTHONPATH=source; PY=.venv/bin/python
DUMP_OUT=tools/superkek/sectors.json $PY tools/superkek/dump.py --customizer tools/superkek/base_coupled.yaml --suppress_rom --spoiler none --outputpath /tmp/dump --seed 1
KEYCAP_OUT=tools/superkek/keycap.json $PY tools/superkek/keycap.py --customizer tools/superkek/base_coupled.yaml --suppress_rom --spoiler none --outputpath /tmp/dump --seed 1
$PY tools/superkek/build_solutions.py        # a few minutes (Desert/TR search 3 extra sectors)
```

## Rolling: Super Kek Priest (coupled)

```bash
cd tools/superkek; PY=../../.venv/bin/python
# 1. build + roll candidates (seed numbers are your choice; failures print why)
ROLL_TMO=150 PAR=2 $PY megarun.py 1000 8
#    -> "1000: ROLLED | AT=45 HC=117 keys AT=0 HC=4 | build 3s roll 77s"   (~75% roll)
# 2. progression into HC/AT for the ones that rolled. EXTRA_SETTINGS must be the same as in step 3: twopass runs
#    both passes with them, otherwise enemizer reshuffles the final fill and progression lands outside HC/AT
export EXTRA_SETTINGS='{"shuffleenemies": "shuffled", "any_enemy_logic": "none", "shufflebosses": "full", "dungeon_counters": "on", "collection_rate": true}'
PAR=2 $PY twopass.py mega 1000,1001,1002,1003
#    -> "seed 1000: layout identical=True; ok: 38/38 progression items in HC/AT"
# 3. final BPS with the per-seed settings (plain or pb = pseudo boots)
OUTDIR=final PAR=2 $PY final.py 1000:DR_superkekpriest_1003:plain 1001:DR_superkekpriest_1004:plain \
                                  1002:DR_superkekpriest_PB_2003:pb 1003:DR_superkekpriest_PB_2004:pb
#    -> "ok bps=... escape=ok layout_same=True prog 38/39 outside=["Hammer@Link's Uncle"] HC=117 AT=45 bosses=12"
# 4. check before publishing
$PY verify.py final/DR_superkekpriest_1003 final/DR_superkekpriest_PB_2003
```

Coupled mega key doors: megagen plandos a random 0-11 key doors in each of HC/AT (`MEGA_KEYS_MAX`, default 11)
and DR tops HC/AT up to its cap of 11. (Setting `FORCE_NONKEY=1` types every other key-capable door as non-key so
DR adds none; it works coupled but is slower to roll and was not used for the published seeds.)

## Rolling: Super Kek Priest 64 (decoupled)

```bash
cd tools/superkek; PY=../../.venv/bin/python
DECOUPLED=1 MEGA_KEYS_MAX=0 SKIP_PT=1 ROLL_TMO=150 BASE_YAML=$PWD/base_decoupled.yaml PAR=3 $PY megarun.py 2000 6
#    -> "2000: ROLLED ..." build 3-90s, roll 45-105s; 6/6 rolled in the last batch
SKIP_PT=1 PAR=2 TMO=200 $PY twopass.py mega 2000,2001
SKIP_PT=1 OUTDIR=final_dec PAR=2 $PY final.py 2000:DR_superkekpriest64_PB_3003:pb 2001:DR_superkekpriest64_PB_3004:pb
$PY verify.py final_dec/DR_superkekpriest64_PB_3003 final_dec/DR_superkekpriest64_PB_3004
```

Decoupled specifics, each one learned from a failure:

- `MEGA_KEYS_MAX=0`: our random key doors on one-way layouts were usually invalid ("Bad dungeon ... invalid custom
  key door"), and forcing non-key types (`FORCE_NONKEY`) overflows the 4-stateful-doors-per-supertile limit
  because typing a one-way door also types its target. So we plando none and DR picks HC/AT key doors (11 each).
- `SKIP_PT=1` (`--skip_playthrough`): DR's spoiler playthrough copies the world and the copy loses one-way plando
  connections ("No path to Throne Room found", "Not all progression items reachable"). The real world is fine;
  the fill already guarantees reachability. The spoiler is still written, without the playthrough section.
- `key_logic_algorithm: strict`, `trap_door_mode: oneway`, `standardize_palettes: original` are in
  `base_decoupled.yaml`; see the settings table for why.

## Escape checkpoint (throne room)

Standard mode's escape has a checkpoint at the throne room: once Zelda opens the tapestry, death or save & quit
respawns you in the throne room (SRAM `StartingEntrance` $04), and from there the only way on is through
`Hyrule Castle Throne Room N`. DR normally guarantees Sanctuary sits behind that door by splitting standard HC into
a "Dungeon" half and a "Sewers" half (`split_dungeon_builder`). A fully plando'd HC is kept whole (PR #13 fix 1),
so DR's split does not apply and megagen has to do it:

- Dungeon half: the HC South/West/East lobbies, Zelda's cell, the throne room, and every other HC room not picked
  for the sewers. Sewers half: Sanctuary plus about `SEWERS_TARGET` supertiles (default 10). Swamp Lobby /
  Swamp Entrance never go in the sewers half: their moat needs the overworld floodgate, which stays shut until
  Zelda is delivered (a throne room link into Swamp Lobby failed fill with "Unable to place dungeon prizes").
- `Throne Room N` is paired with a south door in the sewers half (DR's own rule: a south door of a sector with other
  exits). That pair is two-way even in decoupled mode and is never a key door. Every other door pairs within its
  own half, and each half is polarity-balanced on its own.
- The sewers half must reach Sanctuary from the throne room link (`check_valid` path); the dungeon half keeps DR's
  standard paths (cell -> throne room, cell -> HC South, ...).
- `analyze.py` prints `ESCAPE ok` or `ESCAPE BYPASS: <door path>` on every roll: a search from the castle lobbies
  and the cell that ignores item rules and does not cross the tapestry must not find Sanctuary. `megarun` rejects
  a bypass, and `final.py` prints `escape=ok|BYPASS`.

The first published seeds were made before this (one-piece HC, `HC_SPLIT=0`), with Sanctuary reachable without
the throne room. Five were replaced with split-HC rolls; PB_2001 still has the old layout.

## Time budget and watching runs

Per seed: build (pick + megagen) 2-90 s, roll 45-105 s, two-pass ~2x roll, final ~1 roll. A batch of 6 at PAR 3 is
~5 minutes to six results. **Check results as each seed finishes** (`megarun` prints one line per seed; the roll
log is `mega/roll<seed>/log.txt`, the build log `mega/build<seed>.log`). A roll still running after ~2 minutes is
stuck in a search: look at the last log line (`time elapsed ... iterations/s` = key door search) and kill it
rather than waiting. `ROLL_TMO` is the hard cap per roll.

## Tuning knobs (env vars)

| Var | Script | Meaning |
|---|---|---|
| `AT_TARGET` | megarun/megagen | AT size in supertiles (default 40). Stitcher has built up to ~118; more AT starves the rest. |
| `MEGA_KEYS_MAX` | megagen | max random plando key doors per mega dungeon (default 11) |
| `FORCE_NONKEY` | megagen | type every other key-capable door non-key (coupled only) |
| `SMALL_TYPE` | megagen | type used to block key doors (default `Bomb Door`) |
| `HERA_KEYS` | megagen | plando Hera's two vanilla key doors (off; DR's own choice works with the PR #13 fix) |
| `DECOUPLED` | megagen | one-way layouts |
| `BASE_YAML`, `SOLS` | megarun | base settings file, solutions file |
| `PAR`, `ROLL_TMO`, `SKIP_PT` | megarun/twopass/final | parallelism, roll timeout, skip playthrough |
| `EXTRA_SETTINGS`, `OUTDIR` | final | JSON settings merged into the final roll, output dir |
| `RESERVE_MULT` | twopass | reserved HC/AT locations per progression item (default 2) |
| `MEGA_DEBUG`, `ASSIGN_TRIES` | megagen | print why wiring failed, cap AT-assignment attempts |
| `HC_SPLIT` | megagen | `0` = one-piece HC, as in the published seeds (Sanctuary reachable without the throne room) |
| `SEWERS_TARGET` | megagen | supertiles in HC's sewers half, behind the throne room (default 10) |

## Publishing

Patches live in the public repo `CVW-HMB/alttpr-seeds` (GitHub Pages `https://cvw-hmb.github.io/alttpr-seeds/`),
under `seed/<name>.bps`. Names: `DR_superkekpriest_<n>.bps`, `DR_superkekpriest_PB_<n>.bps` (pseudo boots),
`DR_superkekpriest64_PB_<n>.bps`. Plain 1001+, pseudo boots 2001+, 64 mode 3001+; next free: 1003, 2003, 3003.
Use fresh DR seed numbers for new seeds (not ones already published).

```bash
gh repo clone CVW-HMB/alttpr-seeds /tmp/alttpr-seeds   # or git pull an existing clone
cp final/<name>/*.bps /tmp/alttpr-seeds/seed/<name>.bps
cd /tmp/alttpr-seeds && git add seed/<name>.bps && git commit -m "add ..." && git push
# Pages takes ~30-60 s; confirm the live file is byte-identical before posting:
curl -s https://cvw-hmb.github.io/alttpr-seeds/seed/<name>.bps -o /tmp/live.bps && cmp /tmp/live.bps final/<name>/*.bps
```

Player link (seed field on the async site):
`https://alttprpatch.synack.live/patcher.html?patch=` + URL-encoded `https://cvw-hmb.github.io/alttpr-seeds/seed/<name>.bps`.

## Async site (alttprasyncs.com)

Logged in as homemadebeer in Chrome. Series 51 "HMB Test Modes" (`https://alttprasyncs.com/series/51`) holds these.

1. `https://alttprasyncs.com/yourasyncs`, form "Create New Async" (2nd form on the page): `seed` = patcher link,
   `mode` = "Super Kek Priest" / "Super Kek Priest 64", `hash1`..`hash5` = icon names from `verify.py`
   (site names: "Empty Bottle" not "Bottle", "Bombs", "Green Potion", "Ice Rod", "Moon Pearl", "Magic Powder",
   "Somaria", "Flute", "Bugnet", "Big Key"), `description`. All checkboxes off (spoiler, co-op, login, VOD, edits).
2. Submit leads to a confirm page ("The mode for this seed was not found..."). Check the icons, click
   **This is correct!**. A raw `fetch` POST to `/createasync` only returns that confirm page and creates nothing.
3. Fill the form via JS and click the submit button via `element.click()`; screenshot-coordinate clicks missed.
   Wait for page load before touching `document.forms`.
4. Confirm creation by fetching `/yourasyncs` and finding the row; note the async id (`/editasync/<id>`).
5. Add to series: on `/yourasyncs`, set `select[name=seed_<id>]` to `51` for the new rows only, click
   **Add to Series** (1st form). Check `/series/51`.
6. Editing (e.g. a hash after re-rolling): `/editasync/<id>`, change fields, **Save Changes**, no confirm page.
   A fetch POST of the edited form works here.

## Published seeds

| Name | Async | Mode | PB | Hash | HC / AT supertiles |
|---|---|---|---|---|---|
| DR_superkekpriest_1001 | 32158 | Super Kek Priest | no | Empty Bottle, Ice Rod, Magic Powder, Big Key, Boots | 121 / 39 |
| DR_superkekpriest_1002 | 32159 | Super Kek Priest | no | Somaria, Empty Bottle, Moon Pearl, Flute, Boots | 116 / 50 |
| DR_superkekpriest_PB_2001 | 32160 | Super Kek Priest | yes | Shovel, Heart, Magic Powder, Boomerang, Mirror | 113 / 48 |
| DR_superkekpriest_PB_2002 | 32161 | Super Kek Priest | yes | Cape, Map, Compass, Pendant, Pendant | 130 / 36 |
| DR_superkekpriest64_PB_3001 | 32166 | Super Kek Priest 64 | yes | Cape, Compass, Bombs, Somaria, Flute | 121 / 42 |
| DR_superkekpriest64_PB_3002 | 32167 | Super Kek Priest 64 | yes | Quake, Gloves, Bugnet, Tunic, Hammer | 115 / 53 |

Seed numbers, spoilers, the exact final customizer files and the BPS of every published seed are in the private
archive kept outside the repo by the maintainer (not in git: this repo is public and
the pipeline is deterministic, so a seed number would let anyone regenerate a live async's spoiler). Its README
shows how to regenerate any of them exactly. **Never commit seed numbers or spoilers of live seeds here.**

History (all replacements in place: same file names and asyncs, new layouts and DR seeds, async hashes edited):
- 2026-10-02: every seed except PB_2001 re-rolled with the split HC (Sanctuary only past the throne room).
- 2026-10-03: 1001, 1002, PB_2002 and 64_PB_3002 re-rolled again with keysanity and the money balancing fix.
- PB_2001 and 64_PB_3001 were played, so they stay as they are: neither has keysanity, and PB_2001 is the one
  published seed where Sanctuary is reachable without the throne room. **Never replace a seed that has runs.**

The first four were first posted without enemizer, then re-rolled in place (same seed numbers and layouts, new
hashes) with enemizer, full bosses and counters; the async hashes were edited to match.

## DR changes this depends on (PR #13, `fix/closed-split-dungeon-and-forced-bd-doors`, plus money balancing)

1. `main_dungeon_generation`: a fully plando'd Desert/Skull/standard HC stays unsplit but its name was still
   truncated ("Desert") -> `KeyError: 'Desert'`. Only strip the suffix for sub-builders.
2. `find_valid_bd_combination`: forced bomb/dash doors beyond the suggestion made a negative sample count ->
   `ValueError: Sample larger than population`. Floor at 0.
3. `find_valid_combination`: a layout passing `validate_key_layout` could still raise in `analyze_dungeon`
   ("Unable to find door permutation"; Hera with 1-2 key doors when decoupled, tiny dungeons with 1). Now treated
   as an invalid layout so DR lowers the key count (`analyzes_cleanly`).
4. `patch_rom` boss indicator: boss regions with no recorded entrance (decoupled) raised `StopIteration`. Keep the
   default byte.

5. Money balancing: **a seed must never spawn money.** The tools branch has aerinon/ALttPDoorRandomizer#178
   (skip locked shop slots, i.e. vanilla shop stock, as purchases; tests in `test/TestMoneyBalance.py`) plus the
   no-mint change: when no later rupee is worth more, the balancer stops and warns instead of turning an early
   location into a new Rupees (300). DoorDevUnstable (fork and upstream) still has the minting fallback. Check:
   in `exported_custom.yaml`, `item_pool` (recorded before balancing) and `placements` must have the same
   Rupees (300) count.

Regression tests: `test/TestPlandoClosedDungeons.py`. Full suite: 215 pre-existing failures before and after.

## Failure catalogue (what broke and the fix now in place)

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'Desert'/'Skull'/'Hyrule'` | closed split dungeon name truncation | PR #13 fix 1 |
| "Generation taking too long ... Ref X" in ms | a pre-wired dungeon fails DR's `check_valid` (unreachable regions) | wire layouts with DR's explorer (megagen), not by door counting |
| "No valid destinations" / Desert connectedness | lobby labels ignored Desert/Skull split halves and passage rules | megagen wires small dungeons with DR's entrance list (`entrances_map`) |
| unreachable regions in small dungeons | sectors are not internally connected (one-way ledges, e.g. Mire Right Bridge) | explorer-based wiring; drop dead-end lobby doors in multi-door rooms |
| TR "Generation taking too long" | TR Main labelled onto the dead-end boss room | anchor TR Main/Desert South/Skull 2 East to a networked lobby (pick.py `ANCHOR`) |
| island room after self-loops | room whose only exits are stairs | filtered in `build_solutions.py` |
| "Unable to find door permutation" (KEYFAIL) | DR key analysis bug in tiny dungeons | zero key doors outside HC/AT (filters + `Bomb Door` on connectors/interiors) and PR #13 fix 3 |
| "custom bk doors are bad" (GT) | big key validator needs one ordinary location | require a non-boss location per small dungeon |
| "Only 4 stateful doors per supertile" | forced type on a door outside slots 0-3, or on a one-way target | only type doors in slots 0-3; no forced types in decoupled mega dungeons |
| `ValueError: Sample larger than population` | forced bomb doors beyond suggestion | PR #13 fix 2 |
| `assign_non_hc_sectors` IndexError, or "Unable to place dungeon prizes" with Swamp Lobby in HC | Swamp lobby (floodgate) must leave HC in standard | AT always includes the Swamp Lobby / Swamp Entrance sectors (matched by region: `item_logic` is empty in megagen because it replaces DR's `create_dungeon_builders`) |
| "no more neutral pairings" / balancing hangs | DR's polarity balancing with only HC/AT open | close every dungeon (all plando) so DR does no balancing |
| roll stuck in "time elapsed ... iterations/s" | DR key-door search (decoupled + partial) | strict key logic, `MEGA_KEYS_MAX=0` for decoupled |
| `list.remove(x)` in `change_door_to_trap` | trap code on one-way doors | `trap_door_mode: oneway` (decoupled) |
| StopIteration in `palette_assignment` | palette code on one-way doors | `standardize_palettes: original` (decoupled) |
| "No path to Throne Room" in `copy_world` | spoiler playthrough copy loses one-way plando | `--skip_playthrough` (decoupled) |
| StopIteration in boss indicator | boss region without entrance (decoupled) | PR #13 fix 4 |
| FillError small key (AT/escape) in two-pass | PreferredLocationGroup reserves its locations | reserve <= half of each dungeon's locations, skip key drop/pot key spots |
| bottles outside HC/AT | pass 2 re-rolls bottle contents | list every bottle variant |
| final has 1-2 progression items outside HC/AT although pass 2 had 38/38 (coupled) | pass 2 ran without the enemizer settings final.py adds | twopass applies `EXTRA_SETTINGS` to both passes |
| `ESCAPE BYPASS` (Sanctuary reachable without the throne room; true of the first published seeds) | one-piece HC; fully plando'd HC skips DR's Dungeon/Sewers split | megagen splits HC itself (`HC_SPLIT`, default on) |

## Things tried that did not work (do not repeat)

- **Classic generator grows HC/AT** (minimize other dungeons one by one): reliable to 4 minimized dungeons
  (HC ~32), 3/8 at 5-6, 0/8 from Thieves on: DR's polarity balancing cannot spread 150+ sectors over few dungeons.
- **Pre-clumping leftover sectors into balanced groups** so balancing is trivial: fast failures instead of hangs,
  but HC standard split, crystal and Desert/Skull assertions kept failing.
- **HC ratchet** (freeze HC pairs from the best seed each round): HC 35 -> 61 in one round, abandoned once full
  self-built layouts worked.
- **NewGeneration branch**: has boss-room lobbies for 9 dungeons (1-room dungeons) and `biased` mega-dungeon
  generation, but biased stitching of a mega HC took 20+ min and NG crashes in standard mode on an undefined `b1`
  in `main_dungeon_generation_prototype` (HC sewers merge). Classic path on NG has the same split-name bug.
- **Re-rolling a fully exported layout** to place items: crashed on the split-name bug before PR #13; now the
  two-pass reuses the pass-1 plando with the same seed instead (layout identical, checked).

## Session notes

- `door_self_loops` lets a spiral stair lead to itself; the solver treats stairs as free and self-loops leftovers.
- Small dungeon floors with boss-room lobbies need NG (DoorDevUnstable only has Desert/TR/Skull boss rooms as
  lobby-capable doors).
- The user's main checkout (`gitrepos/alttpr/ALttPDoorRandomizer`) was left on its own branch with its own
  uncommitted work; all of this was done in separate worktrees.
