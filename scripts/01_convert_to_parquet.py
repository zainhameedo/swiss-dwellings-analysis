"""Convert the raw Swiss Dwellings CSVs to zstd Parquet.

Raw CSVs are immutable and stay in data/raw/. DuckDB streams the conversion,
so peak memory stays well under the 4 GB limit set below.
"""
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
INTERIM.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute("SET memory_limit='4GB'")
con.execute("SET preserve_insertion_order=false")

for name in ("geometries", "simulations"):
    src, dst = RAW / f"{name}.csv", INTERIM / f"{name}.parquet"
    t0 = time.time()
    con.execute(
        f"COPY (SELECT * FROM read_csv_auto('{src.as_posix()}', sample_size=200000)) "
        f"TO '{dst.as_posix()}' (FORMAT parquet, COMPRESSION zstd)"
    )
    src_mb, dst_mb = src.stat().st_size / 1e6, dst.stat().st_size / 1e6
    print(f"{name:12s} {src_mb:8.1f} MB -> {dst_mb:7.1f} MB "
          f"({src_mb / dst_mb:4.1f}x)  in {time.time() - t0:5.1f}s")
