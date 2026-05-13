"""Sprint 1 Monday morning bulk ingest orchestrator.

Runs the 10 source-authority downloads concurrently, then dispatches to the
per-source parsers and writes parquet output for the merge pass.

Usage:
    python scripts/sprint1_download_all.py [--sources LOINC,HPO,...] \\
                                            [--skip-download] \\
                                            [--out data/foundation/staging]

The script is idempotent — re-running picks up cached downloads. Designed for
weekend supervised execution: launch it Monday AM, let it run.

Manual-staged sources (require login or email-link workflow):
- LOINC: free login required; download ZIP from https://loinc.org/downloads/
  and place at data/sources/loinc/Loinc_<version>.zip before running.
- Athena: vocabulary picker → submit → email link delivers ZIP. Place at
  data/sources/athena/ before running.

TBD source (Sprint 1 investigation):
- NINDS-CDE: no documented bulk export endpoint. Either probe the catalog
  for a hidden export URL Monday AM, or email NINDSCDE@emmes.com.

Auto-fetched sources (no manual step — orchestrator handles):
- HPO, Mondo, DUO, BIDS — git clone
- CDISC — direct HTTP from NCI EVS FTP
- PhenX — direct HTTP from PhenX Toolkit (auto-extracts ZIP)
- DICOM — bundled in pydicom
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Add repo root to path so this script works from anywhere
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rop.ingest import SOURCES, DEFAULT_SOURCES_DIR, DEFAULT_STAGING_DIR
from rop.ingest._common import write_manifest, DownloadResult


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("sprint1_orchestrator")


def download_phase(sources_dir: Path, skip: set[str]) -> list[DownloadResult]:
    """Run auto-downloadable sources in parallel.

    Auto-downloadable sources fall into three patterns:
      - git clones (HPO, Mondo, DUO, BIDS) — shallow clone via git_clone()
      - direct HTTP files (CDISC) — http_download() to staging dir
      - HTTP + archive extract (PhenX) — http_download() then extract_archive()

    Manual-staged sources (LOINC, Athena, NINDS-CDE) are skipped here —
    they expect pre-staged files. LOINC requires login; Athena requires
    the email-link workflow; NINDS-CDE has no documented bulk export.
    """
    auto = {
        "hpo": SOURCES["hpo"].download_hpo,
        "mondo": SOURCES["mondo"].download_mondo,
        "duo": SOURCES["duo"].download_duo,
        "bids": SOURCES["bids"].download_bids,
        "cdisc": SOURCES["cdisc"].download_cdisc,
        "phenx": SOURCES["phenx"].download_phenx,
    }
    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(fn, sources_dir): name
            for name, fn in auto.items() if name not in skip
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                r = fut.result()
                results.append(r)
                logger.info("%s download complete (cached=%s, %s bytes)",
                           name, r.cached, r.bytes_downloaded)
            except Exception as exc:
                logger.error("%s download failed: %s", name, exc)
    return results


def ingest_phase(sources_dir: Path, staging: Path,
                 sources: list[str]) -> list:
    """Run each source ingest, write per-source parquet (if pyarrow available)
    or JSONL fallback.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        have_parquet = True
    except ImportError:
        logger.warning("pyarrow not installed; falling back to JSONL output")
        have_parquet = False

    staging.mkdir(parents=True, exist_ok=True)
    all_stats = []

    for source_name in sources:
        if source_name not in SOURCES:
            logger.warning("Unknown source: %s; skipping", source_name)
            continue

        module = SOURCES[source_name]
        out_path = staging / f"{source_name}.{'parquet' if have_parquet else 'jsonl'}"
        logger.info("Ingesting %s → %s", source_name, out_path)
        t0 = time.time()
        rows_yielded = 0
        rows = []

        try:
            ingest_fn = getattr(module, f"ingest_{source_name}",
                              None) or module.ingest_athena  # athena is special name
            # Find the right ingest function on the module
            for fn_name in dir(module):
                if fn_name.startswith("ingest_") and callable(getattr(module, fn_name)):
                    ingest_fn = getattr(module, fn_name)
                    break

            for elem in ingest_fn(sources_dir=sources_dir):
                rows.append(elem.model_dump(mode="json"))
                rows_yielded += 1
                if rows_yielded % 50000 == 0:
                    logger.info("  %s: %d rows yielded so far", source_name, rows_yielded)
        except FileNotFoundError as exc:
            logger.warning("%s skipped (source files not staged): %s", source_name, exc)
            continue
        except Exception as exc:
            logger.exception("%s ingest failed: %s", source_name, exc)
            continue

        elapsed = time.time() - t0
        if rows:
            if have_parquet:
                table = pa.Table.from_pylist(rows)
                pq.write_table(table, out_path)
            else:
                with out_path.open("w") as f:
                    for r in rows:
                        f.write(json.dumps(r, default=str) + "\n")

        from rop.ingest._common import IngestStats
        stats = IngestStats(
            source_name=source_name,
            rows_yielded=rows_yielded,
            elapsed_seconds=elapsed,
            output_path=out_path if rows else None,
        )
        all_stats.append(stats)
        logger.info("%s: %d rows in %.1fs", source_name, rows_yielded, elapsed)

    return all_stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources", default="all",
        help="Comma-separated source names (default: all). "
             f"Valid: {','.join(SOURCES.keys())}"
    )
    parser.add_argument(
        "--sources-dir", default=str(DEFAULT_SOURCES_DIR),
        help="Where source files live"
    )
    parser.add_argument(
        "--staging-dir", default=str(DEFAULT_STAGING_DIR),
        help="Where parsed parquet output lands"
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip the git-clone phase; assume sources already on disk"
    )
    parser.add_argument(
        "--skip-ingest", action="store_true",
        help="Only download; don't run parsers"
    )
    args = parser.parse_args()

    sources_dir = Path(args.sources_dir)
    staging = Path(args.staging_dir)

    if args.sources == "all":
        sources = list(SOURCES.keys())
    else:
        sources = [s.strip() for s in args.sources.split(",")]

    logger.info("=" * 70)
    logger.info("Sprint 1 bulk ingest orchestrator")
    logger.info("Sources: %s", sources)
    logger.info("Sources dir: %s", sources_dir)
    logger.info("Staging dir: %s", staging)
    logger.info("=" * 70)

    downloads = []
    if not args.skip_download:
        downloads = download_phase(sources_dir, set())

    stats = []
    if not args.skip_ingest:
        stats = ingest_phase(sources_dir, staging, sources)

    manifest_path = write_manifest(staging, downloads, stats)
    logger.info("Manifest: %s", manifest_path)

    total_rows = sum(s.rows_yielded for s in stats)
    total_secs = sum(s.elapsed_seconds for s in stats)
    logger.info("=" * 70)
    logger.info("Total: %d rows ingested in %.1fs across %d sources",
               total_rows, total_secs, len(stats))


if __name__ == "__main__":
    main()
