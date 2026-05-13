"""Ingest boutique CDE collections from CSV files.

Extracts collection name from filename (e.g., "SEA-AD_cdes.csv" → "SEA-AD").
Tags each CDE with member_of_collections.

Usage:
    python scripts/ingest_boutique_cdes.py \\
        --input boutique-May4th2026 \\
        --output data/boutique/staging/boutique_cdes.parquet
"""
import argparse
import csv
import json
import logging
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("boutique")


def extract_collection_name(filepath: Path) -> str:
    """Extract collection name from filename (e.g., 'SEA-AD_cdes.csv' → 'SEA-AD')."""
    name = filepath.stem  # Remove .csv
    if name.endswith("_cdes") or name.endswith("_CDEs"):
        name = name[:-5]  # Remove _cdes/_CDEs suffix
    # Handle special cases
    if "Answer ALS" in name:
        name = "Answer-ALS"
    elif "CARD_and_PathND" in name:
        name = "CARD-PathND"
    elif name.startswith("GP2"):
        name = "GP2"  # GP2_39 → GP2
    return name


def parse_boutique_csv(filepath: Path) -> list[dict]:
    """Parse boutique CDE CSV into RoP element records."""
    collection_name = extract_collection_name(filepath)
    logger.info("Parsing %s (collection: %s)", filepath.name, collection_name)

    rows = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        # Increase field size limit for large fields
        csv.field_size_limit(10 * 1024 * 1024)
        reader = csv.DictReader(f)

        for row in reader:
            # Extract fields
            source = row.get("Source", collection_name)
            collection = row.get("Collection", "")
            item = row.get("Item", "")
            description = row.get("Description", "")
            item_type = row.get("ItemType", "")
            required = row.get("Required", "")
            values = row.get("Values", "")
            comments = row.get("Comments", "")

            # Build RoPElement-compatible record
            element = {
                "rop_id": str(uuid4()),
                "description": description or f"{item} ({collection})",
                "source_authority": "DataTecnica-boutique",
                "source_code": item,
                "source_version": "2026.05",
                "source_retrieved_date": "2026-05-04",
                "curation_status": "reviewed",
                "member_of_collections": [collection_name],  # Tag with collection
                "metadata_": {
                    "boutique_source": source,
                    "boutique_collection": collection,
                    "boutique_item": item,
                    "boutique_item_type": item_type,
                    "boutique_required": required,
                    "boutique_values": values,
                    "boutique_comments": comments,
                    "alternate_names": row.get("AlternateItemNames", ""),
                    "alternate_description": row.get("AlternateDescription", ""),
                    "priority": row.get("Priority", ""),
                    "related_cdes": row.get("Related_CDEs", ""),
                    "nacc_variable": row.get("nacc_variable", ""),
                    "nacc_mapping": row.get("nacc_mapping", ""),
                    "original_item": row.get("original_item", ""),
                    "original_values": row.get("original_values", ""),
                    "value_mapping": row.get("value_mapping", ""),
                }
            }

            rows.append(element)

    logger.info("  Parsed %d CDEs from %s", len(rows), filepath.name)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input directory with *_cdes.csv files")
    parser.add_argument("--output", required=True, help="Output parquet file")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Find all boutique CDE CSV files
    csv_files = list(input_dir.glob("*.csv"))
    logger.info("Found %d boutique CDE CSV files", len(csv_files))

    all_elements = []
    for csv_file in sorted(csv_files):
        elements = parse_boutique_csv(csv_file)
        all_elements.extend(elements)

    logger.info("Total boutique CDEs parsed: %d", len(all_elements))

    # Convert to PyArrow table
    # Simple schema - full RoPElement schema enforcement happens in merge step
    schema = pa.schema([
        ("rop_id", pa.string()),
        ("description", pa.string()),
        ("source_authority", pa.string()),
        ("source_code", pa.string()),
        ("source_version", pa.string()),
        ("source_retrieved_date", pa.string()),
        ("curation_status", pa.string()),
        ("member_of_collections", pa.list_(pa.string())),
        ("metadata_", pa.string()),  # JSON string for now
    ])

    # Prepare rows for table
    table_data = {
        "rop_id": [e["rop_id"] for e in all_elements],
        "description": [e["description"] for e in all_elements],
        "source_authority": [e["source_authority"] for e in all_elements],
        "source_code": [e["source_code"] for e in all_elements],
        "source_version": [e["source_version"] for e in all_elements],
        "source_retrieved_date": [e["source_retrieved_date"] for e in all_elements],
        "curation_status": [e["curation_status"] for e in all_elements],
        "member_of_collections": [e["member_of_collections"] for e in all_elements],
        "metadata_": [json.dumps(e["metadata_"]) for e in all_elements],
    }

    table = pa.table(table_data, schema=schema)

    # Write parquet
    logger.info("Writing %d rows to %s", len(all_elements), output_path)
    pq.write_table(table, output_path)

    logger.info("✅ Boutique CDEs ingested successfully")
    logger.info("   Collections: %s",
               ", ".join(sorted(set(e["member_of_collections"][0] for e in all_elements))))


if __name__ == "__main__":
    main()
