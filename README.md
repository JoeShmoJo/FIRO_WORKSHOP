# Ephemeral

Willamette Valley Project analysis scripts, plus the Git and pull-request
reference sheets.

## Layout

Each workflow owns a folder under `src/`, `data/` and `out/`. Inputs shared by
more than one workflow stay at the root of `data/`.

| Path | Holds |
|---|---|
| `src/boat_ramps/` | Pool elevation download and the boat ramp day analysis |
| `src/gauges/` | Outflow gauge resolution and the basin map |
| `src/firo/` | Elevation-storage ratings and the FIRO space concept figure |
| `src/DP_DL_28Aug2026.py` | Damages Prevented download (USGS + CWMS, writes DSS) |
| `data/` | `WIL_ELEV_DICT.csv` and `RuleCurves.csv` - shared by several workflows |
| `data/<workflow>/` | Inputs used by one workflow only |
| `out/<workflow>/` | Generated figures and tables |
| `cache/` | USGS and NLDI responses, reused between runs. Not in git |
| `ref/` | Reference material, including the Cowlitz map script the basin map derives from |

## Boat ramp days

```powershell
cd src\boat_ramps ; python download_elevations.py ; if ($?) { python boat_ramp_days.py }
```

`download_elevations.py` pulls ten years of daily pool elevation for the
thirteen projects. Every response is cached under `cache/usgs/`, so a rerun
costs nothing against the USGS request budget and a run interrupted by the rate
limit resumes where it stopped.

`boat_ramp_days.py` counts a ramp for each day the pool is at or above that
ramp's minimum operable elevation, so five usable ramps for a 30-day month is
150 ramp days. It reports that against **rule-curve potential** - the days the
rule curve says the pool should have been above the sill - rather than against
every day in the season, so a project is not charged for the months its own
drawdown schedule puts the pool below a ramp.

Dexter and Big Cliff are excluded: they are re-regulating pools with no rule
curve, and Dexter's ramps sit below its minimum pool.

Three figures come out of it: per-project boxes, per-project elevation duration
against each ramp sill, and `boat_ramp_system.png` - the system on one tile,
with headline numbers, the spread across seasons, and how many of the 35 ramps
were floating on a given day against how many the rule curve called for.

`plot_rule_curves.py` writes `out/boat_ramps/rule_curve_check.html` - pool
elevation against the rule curve, one interactive panel per reservoir, with
ramp sills drawn in. That is the audit: it shows whether the curve sits in the
pool's real operating band, and where the pool ran above or below it. Days with
no observation are drawn as breaks rather than joined, and the script prints
how many each pool is missing.

```powershell
cd src\boat_ramps ; python plot_rule_curves.py
```

A project can read above 100%. That is not an error: the rule curve is a
schedule, and a pool held above it floats ramps the schedule never promised.
`surplus_days` and `deficit_days` in the summary say which way it went - Fern
Ridge's curve drops to 353 ft in November while its lowest ramp is at 364, so
a slow autumn drawdown shows up as surplus.

## FIRO space

```powershell
cd src\firo ; python parse_stor_ratings.py ; if ($?) { python plot_firo_space.py }
```

`parse_stor_ratings.py` turns the elevation-storage rating workbook into one
plain CSV per project under `data/firo/ratings/`, plus `_sources.csv` holding
the CWMS header rows so the provenance and the rating's effective dates survive
the conversion. The CSVs are committed and the workbook is not, on purpose - a
CSV shows up in a pull request diff and an `.xlsx` shows up as "file not
displayed". Drop the workbook at `data/firo/STOR_RATINGS.xlsx`, or pass its
path as the first argument.

`plot_firo_space.py` writes `out/firo/firo_space_concept.png` - one figure for
the idea that Green Peter could be allowed to ride above the conservation rule
curve and below full pool, and that what caps it is not a number of feet but a
**storage volume measured down from full pool**, big enough to absorb the storm
the forecast is calling for. That volume is a function of three things: the
storm's volume, the lead time (which is pre-release, and so is storage you get
back), and the confidence in the forecast (which is carried as a multiplier on
the storm). Panel A puts it on the water year, panels B and C vary one input at
a time.

The model is three lines of arithmetic and is labelled on the figure as a
concept diagram. It has no routing, no inflow shape, and no downstream limit
that moves with stage. It exists to make the shape of the dependence visible,
not to size a pool.

`data/firo/GREEN_PETER_POOL_LEVELS.csv` holds full pool and the two
conservation bookends. **Full pool in it is a placeholder** until the stats tab
of the statistics workbook is parsed into it - every volume on the figure is
measured down from that elevation, so the script prints a warning on every run
until it is replaced. The two conservation rows are derived from
`data/RuleCurves.csv` and are not placeholders. Storages are checked against
the rating on load, and a disagreement bigger than 0.5% is printed - that check
is the datum trap, and it is cheaper to fail there than in a briefing.

## Outflow gauges

```powershell
cd src\gauges ; python find_outflow_gauges.py ; if ($?) { python make_outflow_map.py }
```

## Requirements

`pandas`, `dataretrieval` (1.2.0 or newer), `openpyxl` for the rating
workbook, and for the map `geopandas`, `contextily`, `matplotlib`, `shapely`.

The USGS key goes in `data/usgs_api_key.txt`, which is gitignored. On
dataretrieval 1.2.0 it only raises the request rate limit; downloads work
without one.
