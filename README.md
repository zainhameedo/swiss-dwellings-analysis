# Swiss Dwellings

Analysis of the [Swiss Dwellings dataset](https://zenodo.org/records/7070952) (Zenodo
record 7070952): 42,207 apartments / 242,257 areas across 3,093 buildings on 1,419
Swiss sites, with aggregated simulation results for viewshed, daylight, traffic noise,
connectivity/centrality and layout geometry.

## Layout

```
data/raw/          geometries.csv, simulations.csv   (immutable, as downloaded)
data/interim/      geometries.parquet, simulations.parquet
scripts/           01_convert_to_parquet.py, 02_profile.py, swissdwellings.py
notebooks/         explore.py      (marimo)
reports/figures/
```

## Running

Python is Anaconda 3.12 (`C:\ProgramData\anaconda3`), put on PATH via
`conda init powershell`, so from a fresh PowerShell:

```powershell
# one-off: rebuild the parquet from the raw CSVs
python scripts/01_convert_to_parquet.py

# the notebook
marimo edit notebooks/explore.py
```

The `conda init` hook is what makes this work: `WindowsApps` sits in the *machine*
PATH, which Windows resolves before the user PATH, so the 0-byte Microsoft Store
`python.exe` stub shadows Anaconda no matter how the user PATH is ordered. The
profile hook runs after PATH is built and takes precedence. If `python` ever
resolves to `WindowsApps` again, that hook is the thing that went missing —
fall back to the absolute path `C:\ProgramData\anaconda3\python.exe` meanwhile.

## Data model

| view | rows | grain |
|---|---|---|
| `geo` | 2,501,540 | one row per geometry |
| `sim` | 347,583 | one row per `(floor_id, area_id)`, 367 columns |

Hierarchy: site -> building -> floor -> unit/apartment -> area, with features inside areas.

`geo.entity_type` splits into `area` (416,710 rows, 28 subtypes), `separator`
(1,270,624 — WALL/RAILING/COLUMN), `opening` (569,608 — DOOR/WINDOW/ENTRANCE_DOOR)
and `feature` (244,598 — fixtures).

`sim` columns are named `<category>_<dimensions>_<aggregation>`, where aggregation is
one of `min max mean median p20 p80 stddev`. Counts by family: view 126, sun 126,
connectivity 70, layout 25, window 8, noise 4, plus 8 key/context columns
(`floor_number`, `floor_has_elevator`, and the six ids).

### Two things that will bite

**1. `area_id` is not unique.** A floor plan is drawn once and reused across identical
floors, so the same `area_id` recurs within a site — up to 15 times — with *identical
geometry* but *different* simulation results per floor. Joining on `area_id` alone
fans rows out. The unique key on both tables is `(floor_id, area_id)`; `(unit_id,
area_id)` works too. `sd.join_sim_geo()` does this correctly.

**2. Not every area has a simulation row.** 416,710 area geometries vs 347,583
simulation rows, so an inner join drops areas (typically shafts and voids). Use a
LEFT join when you want the geometry regardless — `sd.floor_plan_with_metric()` does,
and `plot_floor` renders the missing ones in light grey.

Geometry is WKT in each **site's local coordinate system**, in metres, +x east and
+y north. Coordinates are not comparable across sites, so plot one site at a time.

## Helpers

`scripts/swissdwellings.py`:

```python
import sys; sys.path.append("scripts")
import swissdwellings as sd

con = sd.connect()                              # duckdb + `geo` and `sim` views
sd.sim_columns(con, "sun")                      # column names in a family
sd.metric_bases(con, "sun")                     # suffix-stripped metric bases
sd.join_sim_geo(con, ["layout_area"], where="g.site_id = 11111")
sd.to_gdf(df)                                   # WKT column -> GeoDataFrame
sd.floor_geometries(con, floor_id)              # every geometry on one floor
sd.floor_plan_with_metric(con, floor_id, col)   # same, with a metric on the areas
sd.plot_floor(gdf, color_by=col, cmap="inferno")
```

Aggregate in duckdb and pull only what you plot into pandas — `sim` is 367 columns
wide and the machine has ~6 GB of free RAM.

## Notes

- Parquet (zstd) is 605 MB vs 2.29 GB of CSV, and column-pruned reads are much faster.
  Prefer `data/interim/` for everything; `data/raw/` exists so the conversion is
  reproducible.
- Disk was at 98% when this was set up. If space is needed, the raw CSVs are
  re-downloadable from Zenodo and the parquet is a lossless conversion of them.
