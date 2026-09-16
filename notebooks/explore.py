import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo

    # scripts/ holds the shared helpers
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.append(str(ROOT / "scripts"))
    return (mo,)


@app.cell
def _():
    import matplotlib.pyplot as plt
    import pandas as pd

    import swissdwellings as sd

    con = sd.connect()
    return con, plt, sd


@app.cell
def _(mo):
    mo.md("""
    # Swiss Dwellings

    42,207 apartments / 242,257 areas / 3,093 buildings across 1,419 Swiss sites.

    Two tables are registered on the duckdb connection `con`:

    | view | rows | grain |
    |---|---|---|
    | `geo` | 2,501,540 | one row per geometry (area, separator, opening, feature) |
    | `sim` | 347,583 | one row per **(floor_id, area_id)**, 367 columns |

    **Grain warning.** `area_id` is *not* unique. A plan is drawn once and reused
    across identical floors, so the same `area_id` recurs within a site (up to 15x)
    with identical geometry but different simulation results per floor.
    Always join on `(floor_id, area_id)`.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Schema
    """)
    return


@app.cell
def _(con, sd):
    # How many columns each simulation family contributes.
    families = ["layout", "view", "sun", "connectivity", "noise", "window"]
    family_counts = {f: len(sd.sim_columns(con, f)) for f in families}
    family_counts
    return (families,)


@app.cell
def _(families, mo):
    family_picker = mo.ui.dropdown(
        options=families, value="view", label="Metric family"
    )
    family_picker
    return (family_picker,)


@app.cell
def _(con, family_picker, sd):
    # Metric bases in the chosen family. Every base except the layout_* scalars
    # carries the 7 aggregation suffixes in sd.AGGS.
    sd.metric_bases(con, family_picker.value)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Floor plan viewer

    Pick a floor and a metric. `color_by=None` falls back to colouring each
    area by its room type.
    """)
    return


@app.cell
def _(con):
    # Floors with enough areas to be interesting to look at.
    floor_choices = [
        str(r[0])
        for r in con.execute(
            """
            SELECT floor_id FROM geo WHERE entity_type = 'area'
            GROUP BY 1 HAVING count(*) BETWEEN 25 AND 80
            ORDER BY floor_id LIMIT 300
            """
        ).fetchall()
    ]
    return (floor_choices,)


@app.cell
def _(con, floor_choices, mo, sd):
    numeric_metrics = [
        c
        for c in sd.sim_columns(con)
        if c.startswith(("view_", "sun_", "connectivity_", "noise_"))
        or c in ("layout_area", "layout_compactness", "layout_net_area", "layout_perimeter")
    ]

    floor_picker = mo.ui.dropdown(
        options=floor_choices, value=floor_choices[0], label="floor_id"
    )
    metric_picker = mo.ui.dropdown(
        options=["(room type)"] + sorted(numeric_metrics),
        value="(room type)",
        label="Colour by",
    )
    cmap_picker = mo.ui.dropdown(
        options=["viridis", "inferno", "magma", "cividis", "coolwarm", "YlGnBu"],
        value="viridis",
        label="cmap",
    )
    labels_toggle = mo.ui.checkbox(value=True, label="Label rooms")

    mo.hstack([floor_picker, metric_picker, cmap_picker, labels_toggle], justify="start")
    return cmap_picker, floor_picker, labels_toggle, metric_picker


@app.cell
def _(cmap_picker, con, floor_picker, labels_toggle, metric_picker, plt, sd):
    _fid = int(floor_picker.value)
    _metric = None if metric_picker.value == "(room type)" else metric_picker.value

    if _metric is None:
        _gdf = sd.floor_geometries(con, _fid)
        _title = f"Floor {_fid} - room types"
    else:
        _gdf = sd.floor_plan_with_metric(con, _fid, _metric)
        _title = f"Floor {_fid} - {_metric}"

    _fig, _ax = plt.subplots(figsize=(11, 11))
    sd.plot_floor(
        _gdf,
        color_by=_metric,
        ax=_ax,
        cmap=cmap_picker.value,
        title=_title,
        label_rooms=labels_toggle.value,
    )
    _fig
    return


@app.cell
def _(mo):
    mo.md("""
    ## Scratch

    `con` is a duckdb connection, `sd` the helper module. Useful entry points:

    - `sd.sim_columns(con, family)` / `sd.metric_bases(con, family)`
    - `sd.join_sim_geo(con, cols, where=...)` - joins on the correct grain
    - `sd.to_gdf(df)` - WKT column -> GeoDataFrame
    - `sd.floor_geometries(con, floor_id)` / `sd.floor_plan_with_metric(con, floor_id, metric)`
    - `sd.plot_floor(gdf, color_by=...)`

    Aggregate in duckdb, pull only what you plot into pandas.
    """)
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
