"""Shared tooling for the Swiss Dwellings dataset.

Import from a marimo notebook or a script:

    import sys; sys.path.append("scripts")
    import swissdwellings as sd

    con = sd.connect()                    # duckdb, with `geo` and `sim` views
    gdf = sd.floor_geometries(con, floor_id)
    sd.plot_floor(gdf)

GRAIN WARNING
-------------
The unique grain of both tables is (floor_id, area_id) -- NOT area_id.
A floor plan is drawn once and reused across identical floors, so the same
area_id recurs within a site with identical geometry but different simulation
results per floor. Joining on area_id alone fans rows out. Use
sd.JOIN_KEYS or the sd.join_sim_geo() helper.

COORDINATES
-----------
Geometry is WKT in each site's local coordinate system, in metres:
+x points east, +y points north. Coordinates are NOT comparable across sites,
so plot one floor (or one site) at a time.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from shapely import wkt

ROOT = Path(__file__).resolve().parent.parent
INTERIM = ROOT / "data" / "interim"
RAW = ROOT / "data" / "raw"

JOIN_KEYS = ["floor_id", "area_id"]

#: entity_type -> what it contains, for reference when filtering `geo`.
ENTITY_TYPES = {
    "area": "rooms and outdoor areas (ROOM, BATHROOM, BALCONY, ...) -- 28 subtypes",
    "separator": "WALL, RAILING, COLUMN",
    "opening": "DOOR, WINDOW, ENTRANCE_DOOR",
    "feature": "fixtures: KITCHEN, SINK, TOILET, BATHTUB, SHOWER, STAIRS, ...",
}

#: Aggregation suffixes present on every view_/sun_/connectivity_ metric base.
AGGS = ("min", "max", "mean", "median", "p20", "p80", "stddev")

# Fill colours for a floor plan. Anything unlisted falls back to OTHER_COLOR.
ROOM_COLORS = {
    "ROOM": "#d9d2c5", "BEDROOM": "#cfd8e8", "LIVING_ROOM": "#e3d9c0",
    "LIVING_DINING": "#e3d9c0", "DINING": "#e3d9c0", "KITCHEN_DINING": "#e8cfc2",
    "KITCHEN": "#e8cfc2", "BATHROOM": "#c3dcdc", "CORRIDOR": "#ece7dd",
    "STOREROOM": "#ded7cb", "SHAFT": "#b0a89c", "STAIRCASE": "#c8c2b6",
    "ELEVATOR": "#b0a89c", "BALCONY": "#d7e3cf", "LOGGIA": "#d7e3cf",
    "TERRACE": "#d7e3cf", "GARDEN": "#cfe0c3", "PATIO": "#d7e3cf",
    "WINTERGARTEN": "#d7e3cf", "VOID": "#f2f0ec", "LIGHTWELL": "#f2f0ec",
}
OTHER_COLOR = "#e0dcd4"

WALL_COLOR = "#3d3a35"
RAIL_COLOR = "#9a938a"
EDGE_COLOR = "#8a8378"


def connect(memory_limit: str = "4GB") -> duckdb.DuckDBPyConnection:
    """Return a duckdb connection with `geo` and `sim` views over the parquet."""
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(
        f"CREATE VIEW geo AS SELECT * FROM '{(INTERIM / 'geometries.parquet').as_posix()}'"
    )
    con.execute(
        f"CREATE VIEW sim AS SELECT * FROM '{(INTERIM / 'simulations.parquet').as_posix()}'"
    )
    return con


def sim_columns(con, family: str | None = None) -> list[str]:
    """Column names in `sim`, optionally filtered to one family.

    family: 'view' | 'sun' | 'connectivity' | 'layout' | 'window' | 'noise'
    """
    cols = [r[0] for r in con.execute("DESCRIBE sim").fetchall()]
    return [c for c in cols if c.startswith(f"{family}_")] if family else cols


def metric_bases(con, family: str) -> list[str]:
    """Distinct metric bases in a family, with the aggregation suffix stripped."""
    pat = re.compile(rf"_({'|'.join(AGGS)})$")
    return sorted({pat.sub("", c) for c in sim_columns(con, family)})


def join_sim_geo(con, sim_cols: list[str], where: str = "TRUE") -> pd.DataFrame:
    """Join simulation columns onto area geometries on the correct grain.

    `where` is applied to the joined result, e.g. "g.site_id = 11111".
    Returns a plain DataFrame; pass it through to_gdf() to get geometry.
    """
    picked = ", ".join(f"s.{c}" for c in sim_cols)
    return con.execute(f"""
        SELECT g.floor_id, g.area_id, g.site_id, g.building_id, g.unit_id,
               g.apartment_id, g.entity_subtype, g.geometry, {picked}
        FROM geo g
        JOIN sim s USING (floor_id, area_id)
        WHERE g.entity_type = 'area' AND ({where})
    """).df()


def to_gdf(df: pd.DataFrame, geometry_col: str = "geometry") -> gpd.GeoDataFrame:
    """Parse a WKT column into a GeoDataFrame (site-local CRS, so crs=None)."""
    out = df.copy()
    out[geometry_col] = out[geometry_col].map(wkt.loads)
    return gpd.GeoDataFrame(out, geometry=geometry_col, crs=None)


def floor_geometries(
    con,
    floor_id: int,
    entity_types: tuple[str, ...] = ("area", "separator", "opening", "feature"),
) -> gpd.GeoDataFrame:
    """Every geometry on one floor, as a GeoDataFrame."""
    types = ", ".join(f"'{t}'" for t in entity_types)
    df = con.execute(
        f"SELECT * FROM geo WHERE floor_id = ? AND entity_type IN ({types})", [floor_id]
    ).df()
    return to_gdf(df)


def floor_plan_with_metric(con, floor_id: int, metric: str) -> gpd.GeoDataFrame:
    """One floor's geometries with `metric` joined onto the area rows.

    Walls/openings/features come through with the metric as NaN, so the result
    can go straight into plot_floor(..., color_by=metric).
    """
    df = con.execute(f"""
        SELECT g.*, s.{metric} AS {metric}
        FROM geo g
        LEFT JOIN sim s USING (floor_id, area_id)
        WHERE g.floor_id = ?
    """, [floor_id]).df()
    return to_gdf(df)


def sample_floor(con, min_areas: int = 25, seed: int | None = None) -> int:
    """A floor_id with at least `min_areas` areas -- handy for a first plot."""
    if seed is not None:
        con.execute("SELECT setseed(?)", [(seed % 1000) / 1000])
    return con.execute("""
        SELECT floor_id FROM geo WHERE entity_type = 'area'
        GROUP BY 1 HAVING count(*) >= ? ORDER BY random() LIMIT 1
    """, [min_areas]).fetchone()[0]


def plot_floor(gdf: gpd.GeoDataFrame, color_by: str | None = None, *, ax=None,
               cmap: str = "viridis", title: str | None = None, legend: bool = True,
               label_rooms: bool = False, vmin=None, vmax=None):
    """Draw a floor plan.

    color_by=None       -> fill each area by entity_subtype (ROOM_COLORS)
    color_by='<column>' -> choropleth the areas by that numeric column
    Walls are drawn dark, railings lighter, openings and features outlined.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(13, 13))

    areas = gdf[gdf.entity_type == "area"]
    walls = gdf[(gdf.entity_type == "separator") & (gdf.entity_subtype == "WALL")]
    rails = gdf[(gdf.entity_type == "separator") & (gdf.entity_subtype != "WALL")]
    opens = gdf[gdf.entity_type == "opening"]
    feats = gdf[gdf.entity_type == "feature"]

    if color_by is None:
        if not areas.empty:
            areas.plot(ax=ax, edgecolor=EDGE_COLOR, linewidth=0.4, zorder=1,
                       color=[ROOM_COLORS.get(s, OTHER_COLOR) for s in areas.entity_subtype])
            if legend:
                present = list(areas.entity_subtype.value_counts().index)[:14]
                ax.legend(
                    handles=[Patch(facecolor=ROOM_COLORS.get(s, OTHER_COLOR),
                                   edgecolor=EDGE_COLOR, label=s.title().replace("_", " "))
                             for s in present],
                    loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=9)
    else:
        vals = pd.to_numeric(areas[color_by], errors="coerce")
        areas.assign(**{color_by: vals}).plot(
            ax=ax, column=color_by, cmap=cmap, edgecolor=EDGE_COLOR, linewidth=0.4,
            legend=legend, vmin=vmin, vmax=vmax, missing_kwds={"color": "#f0eee9"},
            legend_kwds={"shrink": 0.45, "label": color_by}, zorder=1)

    if not rails.empty:
        rails.plot(ax=ax, color=RAIL_COLOR, linewidth=0, zorder=2)
    if not walls.empty:
        walls.plot(ax=ax, color=WALL_COLOR, linewidth=0, zorder=3)
    if not opens.empty:
        opens.plot(ax=ax, facecolor="white", edgecolor=WALL_COLOR, linewidth=0.5, zorder=4)
    if not feats.empty:
        feats.plot(ax=ax, facecolor="none", edgecolor="#6b655c", linewidth=0.6, zorder=5)

    if label_rooms and not areas.empty:
        for r in areas.itertuples():
            c = r.geometry.representative_point()
            ax.annotate(r.entity_subtype.title().replace("_", " "), (c.x, c.y),
                        ha="center", va="center", fontsize=6, color=WALL_COLOR)

    ax.set_aspect("equal")
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=13, loc="left", color=WALL_COLOR)
    return ax
