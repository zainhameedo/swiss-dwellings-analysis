# Reference notes

**This whole folder is scaffolding Claude wrote, kept only as an escape hatch.
It is not part of the analysis. Peek if you get stuck; otherwise ignore it.**

> **Version caveat.** Everything below was derived from Zenodo record 7070952
> (the two-CSV release: `geometries.csv` + `simulations.csv`). The project has
> since moved to **swiss-dwellings-v3.0.0**, which has a different schema —
> see the table at the bottom. Treat every number here as "true of the old
> release, probably still directionally true, verify before relying on it."

## What's in here

| file | what it is |
|---|---|
| `swissdwellings.py` | duckdb connection, WKT -> GeoDataFrame, floor-plan renderer |
| `explore.py` | marimo notebook: schema browser + interactive plan viewer |
| `02_profile.py` | schema / cardinality profile |
| `03_keytest.py` | primary-key test (the evidence behind the grain finding) |
| `figures/` | two rendered floor plans produced by `plot_floor` |

To run any of it, the helpers live alongside it:

```python
import sys; sys.path.append("reference")
import swissdwellings as sd
```

## Findings from the old release

Shape: 42,207 apartments / 242,257 areas / 3,093 buildings / 1,419 sites.
`geo` 2,501,540 rows; `sim` 347,583 rows and 367 columns.

`geo.entity_type`: `area` (416,710 rows, 28 subtypes), `separator` (1,270,624 —
WALL/RAILING/COLUMN), `opening` (569,608 — DOOR/WINDOW/ENTRANCE_DOOR), `feature`
(244,598 — fixtures).

`sim` columns are `<category>_<dimensions>_<aggregation>`, aggregation one of
`min max mean median p20 p80 stddev`. By family: view 126, sun 126,
connectivity 70, layout 25, window 8, noise 4.

**The grain trap.** `area_id` was *not* unique. The same `area_id` recurred
within a site — up to 15 times — with identical geometry but different
simulation values per floor, because a plan is drawn once and reused across
identical floors. The unique key was `(floor_id, area_id)`. Joining on
`area_id` alone fans rows out silently.

In v3.0.0 there is now an explicit `plan_id` column, which is very likely the
first-class version of exactly this. Worth checking whether the grain is still
`(floor_id, area_id)` or something cleaner.

**Coverage gap.** 416,710 area geometries vs 347,583 simulation rows, so an
inner join silently drops areas (mostly shafts and voids). Left-join if you
want the geometry regardless.

**Coordinates.** WKT in each *site's* local coordinate system, in metres,
+x east and +y north. Not comparable across sites, so plot one site at a time.

## v3.0.0 schema deltas

| | old record | v3.0.0 |
|---|---|---|
| `geometries.csv` | 9 cols | 13 — adds `plan_id`, `unit_usage`, `elevation`, `height` |
| `simulations.csv` | 367 cols | 369 — adds `plan_id`, `unit_usage` |
| `locations.csv` | absent | 503 cols keyed on `building_id` (climate normals, ...) |
| `location_ratings.csv` | absent | 7 cols keyed on `building_id` |

`elevation` and `height` on geometries mean 3D is possible in v3; the old
release was strictly 2D footprints.
