# Swiss Dwellings

Analysis of the [Swiss Dwellings dataset](https://zenodo.org/records/7070952),
**v3.0.0**: apartment models for thousands of Swiss buildings, with aggregated
simulation results for viewshed, daylight, traffic noise, connectivity/centrality
and layout geometry.

Analysis is mine to do. `reference/` is Claude-written scaffolding kept as an
escape hatch — see `reference/NOTES.md`.

## Layout

```
swiss.py            the analysis notebook (marimo)
data/raw/           swiss-dwellings-v3.0.0.zip   (immutable, as downloaded)
data/interim/       *.parquet                    (generated)
scripts/            01_convert_to_parquet.py
reference/          scaffolding - not part of the analysis
reports/
```

## Setup

Python is Anaconda 3.12 (`C:\ProgramData\anaconda3`), put on PATH via
`conda init powershell`. From a fresh PowerShell:

```powershell
python scripts/01_convert_to_parquet.py   # zip -> data/interim/*.parquet
marimo edit swiss.py
```

Installed for this project: `duckdb`, `marimo` (on top of Anaconda's pandas,
geopandas, shapely, matplotlib, scipy, sklearn, statsmodels).

The `conda init` hook is what makes `python` resolve correctly: `WindowsApps`
sits in the *machine* PATH, which Windows resolves before the user PATH, so the
0-byte Microsoft Store `python.exe` stub shadows Anaconda no matter how the user
PATH is ordered. The profile hook runs after PATH is built and takes precedence.
If `python` ever resolves to `WindowsApps` again, that hook is what went missing;
fall back to `C:\ProgramData\anaconda3\python.exe` meanwhile.

## The four tables

| file | grain | cols |
|---|---|---|
| `geometries.csv` | one row per geometry | 13 |
| `simulations.csv` | one row per area | 369 |
| `locations.csv` | `building_id` | 503 |
| `location_ratings.csv` | `building_id` | 7 |

Hierarchy: site -> building -> plan -> floor -> unit/apartment -> area.

Geometry is WKT in each **site's** local coordinate system, in metres, +x east
and +y north — so it is not comparable across sites.

## Working notes

- Prefer `data/interim/` over the raw CSVs: parquet is several times smaller and
  column-pruned reads matter, because `simulations` is 369 columns wide.
- Aggregate in duckdb and pull only what you plot into pandas. The machine has
  ~15 GB RAM and the conversion script caps duckdb at 4 GB.
- **Disk is tight** (97% full). The conversion extracts one CSV at a time and
  deletes it after converting, so peak extra usage stays under ~1.6 GB. The zip
  stays in `data/raw/` so the whole thing is reproducible; `data/` is gitignored.
