import duckdb, pandas as pd
from pathlib import Path
pd.set_option("display.width", 220)
I = (Path(__file__).resolve().parent.parent / "data" / "interim").as_posix()
con = duckdb.connect(); con.execute("SET memory_limit='4GB'")
con.execute(f"CREATE VIEW sim AS SELECT * FROM '{I}/simulations.parquet'")
con.execute(f"CREATE VIEW geo AS SELECT * FROM '{I}/geometries.parquet'")
q = lambda s: print(con.execute(s).df().to_string(index=False))

print("=== candidate keys in sim (347,583 rows) ===")
for k in ["area_id", "(site_id,area_id)", "(floor_id,area_id)", "(unit_id,area_id)",
          "(apartment_id,area_id)", "(unit_id,apartment_id,area_id)"]:
    n = con.execute(f"SELECT count(distinct {k}) FROM sim").fetchone()[0]
    print(f"  {k:34s} -> {n:,}   {'UNIQUE' if n == 347583 else ''}")

print("\n=== candidate keys among geo areas (416,710 rows) ===")
for k in ["area_id", "(floor_id,area_id)", "(unit_id,area_id)", "(apartment_id,area_id)"]:
    n = con.execute(f"SELECT count(distinct {k}) FROM geo WHERE entity_type='area'").fetchone()[0]
    print(f"  {k:34s} -> {n:,}   {'UNIQUE' if n == 416710 else ''}")

print("\n=== inspect one duplicated area_id ===")
aid = con.execute("SELECT area_id FROM sim GROUP BY 1 HAVING count(*)=4 LIMIT 1").fetchone()[0]
q(f"""SELECT area_id, site_id, building_id, floor_id, floor_number, unit_id, apartment_id,
       layout_area_type, round(layout_area,2) layout_area, round(sun_201806211200_mean,1) sun_jun_noon
     FROM sim WHERE area_id={aid} ORDER BY floor_number""")

print("\n=== does geometry differ across those duplicates? ===")
q(f"""SELECT area_id, floor_id, unit_id, count(*) n_rows,
       count(distinct geometry) n_distinct_geom
     FROM geo WHERE area_id={aid} AND entity_type='area' GROUP BY 1,2,3 ORDER BY floor_id""")
