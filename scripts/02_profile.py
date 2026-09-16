import duckdb, pandas as pd
from pathlib import Path
pd.set_option("display.width", 220)
ROOT = Path(__file__).resolve().parent.parent
I = (ROOT / "data" / "interim").as_posix()
con = duckdb.connect(); con.execute("SET memory_limit='4GB'")
con.execute(f"CREATE VIEW sim AS SELECT * FROM '{I}/simulations.parquet'")
con.execute(f"CREATE VIEW geo AS SELECT * FROM '{I}/geometries.parquet'")
q = lambda s: print(con.execute(s).df().to_string(index=False))

print("=== 1. area_id duplication in sim ===")
q("""SELECT n_dupe, count(*) n_area_ids FROM (
      SELECT area_id, count(*) n_dupe FROM sim GROUP BY 1) GROUP BY 1 ORDER BY 1""")

print("\n=== 2. are duplicate area_id rows identical, or different sites? ===")
q("""SELECT count(*) dup_area_ids,
       sum(CASE WHEN n_site>1 THEN 1 ELSE 0 END) spanning_multiple_sites
     FROM (SELECT area_id, count(*) c, count(distinct site_id) n_site
           FROM sim GROUP BY 1 HAVING c>1)""")

print("\n=== 3. same question for geo ===")
q("""SELECT count(*) dup_area_ids,
       sum(CASE WHEN n_site>1 THEN 1 ELSE 0 END) spanning_multiple_sites
     FROM (SELECT area_id, count(*) c, count(distinct site_id) n_site
           FROM geo WHERE entity_type='area' GROUP BY 1 HAVING c>1)""")

print("\n=== 4. is (site_id, area_id) unique in sim? ===")
q("""SELECT count(*) total_rows, count(distinct (site_id, area_id)) distinct_site_area FROM sim""")

print("\n=== 5. is (site_id, area_id) unique among geo areas? ===")
q("""SELECT count(*) total_area_rows, count(distinct (site_id, area_id)) distinct_site_area
     FROM geo WHERE entity_type='area'""")
