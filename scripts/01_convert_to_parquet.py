"""Convert the swiss-dwellings v3.0.0 data to zstd Parquet.

Works from whichever layout data/raw/ is in:

  * loose CSVs (geometries.csv, simulations.csv, locations.csv,
    location_ratings.csv) -- read in place, left untouched; or
  * swiss-dwellings-v3.0.0.zip -- each member extracted, converted, then the
    extracted copy deleted, so peak extra disk stays at the size of the largest
    single CSV (~1.6 GB) rather than the full 2.51 GB. Disk is the binding
    constraint here; the volume runs near full.

DuckDB streams the conversion, so peak memory stays well under the 4 GB limit.

Idempotent: a table whose .parquet already exists is skipped. Delete the
.parquet to force a rebuild.
"""
import shutil
import time
import zipfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
ZIP = RAW / "swiss-dwellings-v3.0.0.zip"

# Largest CSV is ~1.6 GB; keep a margin on top of that before extracting.
MIN_FREE_BYTES = 3 * 1024**3


def free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def convert(con, name: str, csv: Path, csv_size: int, t0: float) -> None:
    """Convert one CSV to parquet and report what landed."""
    dst = INTERIM / f"{name}.parquet"
    con.execute(
        f"COPY (SELECT * FROM read_csv_auto('{csv.as_posix()}', sample_size=200000)) "
        f"TO '{dst.as_posix()}' (FORMAT parquet, COMPRESSION zstd)"
    )
    csv_mb, pq_mb = csv_size / 1e6, dst.stat().st_size / 1e6
    rows = con.execute(f"SELECT count(*) FROM '{dst.as_posix()}'").fetchone()[0]
    cols = len(con.execute(f"DESCRIBE SELECT * FROM '{dst.as_posix()}'").fetchall())
    print(f"{name:20s} {csv_mb:8.1f} MB -> {pq_mb:7.1f} MB ({csv_mb / pq_mb:4.1f}x)  "
          f"{rows:>10,} rows x {cols:>3} cols  in {time.time() - t0:5.1f}s")


def main() -> None:
    loose = sorted(RAW.glob("*.csv"), key=lambda p: p.stat().st_size)
    if not loose and not ZIP.exists():
        raise SystemExit(
            f"nothing to convert in {RAW}\n"
            "Expected the v3.0.0 CSVs, or swiss-dwellings-v3.0.0.zip."
        )

    INTERIM.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'")
    con.execute("SET preserve_insertion_order=false")

    if loose:
        # CSVs already extracted: read in place, leave them alone.
        for csv in loose:
            if (INTERIM / f"{csv.stem}.parquet").exists():
                print(f"{csv.stem:20s} skipped (parquet exists)")
                continue
            convert(con, csv.stem, csv, csv.stat().st_size, time.time())
    else:
        # Only the zip: extract one member at a time and delete after each.
        with zipfile.ZipFile(ZIP) as zf:
            # smallest first, so a disk failure costs least
            entries = sorted(
                (e for e in zf.infolist() if e.filename.endswith(".csv")),
                key=lambda e: e.file_size,
            )
            for entry in entries:
                name = Path(entry.filename).stem
                if (INTERIM / f"{name}.parquet").exists():
                    print(f"{name:20s} skipped (parquet exists)")
                    continue

                need = entry.file_size + MIN_FREE_BYTES
                if free_bytes(RAW) < need:
                    raise SystemExit(
                        f"{name}: need ~{need / 1e9:.1f} GB free to extract safely, "
                        f"have {free_bytes(RAW) / 1e9:.1f} GB. Free some space first."
                    )

                tmp = RAW / Path(entry.filename).name
                t0 = time.time()
                with zf.open(entry) as src, open(tmp, "wb") as out:
                    shutil.copyfileobj(src, out, length=8 * 1024 * 1024)
                try:
                    convert(con, name, tmp, entry.file_size, t0)
                finally:
                    tmp.unlink(missing_ok=True)

    print(f"\ndisk free: {free_bytes(RAW) / 1e9:.1f} GB")


if __name__ == "__main__":
    main()
