#!/usr/bin/env python3
"""Merge boutique CDE collections with foundation bundle.

Combines:
- Foundation bundle: data/foundation/staging/dedup_pass1.parquet (1,326,063 rows)
- Boutique CDEs: data/boutique/staging/boutique_cdes.parquet (2,910 rows)

Output:
- data/final/v2026.04_elements.parquet (1,328,973 rows combined)

Strategy:
1. Load both parquets
2. Concatenate (no dedup needed - boutique CDEs are distinct project-specific collections)
3. Write combined parquet
4. Verify row counts
"""

import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path
import sys

def main():
    foundation_path = Path("data/foundation/staging/dedup_pass1.parquet")
    boutique_path = Path("data/boutique/staging/boutique_cdes.parquet")
    output_path = Path("data/final/v2026.04_elements.parquet")

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("🔄 Merging boutique CDEs with foundation bundle...")
    print(f"   Foundation: {foundation_path}")
    print(f"   Boutique:   {boutique_path}")
    print(f"   Output:     {output_path}")
    print()

    # Load foundation bundle
    print("📖 Loading foundation bundle...")
    foundation_table = pq.read_table(foundation_path)
    foundation_count = foundation_table.num_rows
    print(f"   Foundation rows: {foundation_count:,}")

    # Load boutique CDEs
    print("📖 Loading boutique CDEs...")
    boutique_table = pq.read_table(boutique_path)
    boutique_count = boutique_table.num_rows
    print(f"   Boutique rows:   {boutique_count:,}")
    print()

    # Schema check - ensure compatible schemas
    print("🔍 Checking schema compatibility...")
    foundation_schema = foundation_table.schema
    boutique_schema = boutique_table.schema

    # Get field names
    foundation_fields = set(foundation_schema.names)
    boutique_fields = set(boutique_schema.names)

    # Fields only in foundation
    foundation_only = foundation_fields - boutique_fields
    if foundation_only:
        print(f"   ⚠️  Fields only in foundation: {foundation_only}")

    # Fields only in boutique
    boutique_only = boutique_fields - foundation_fields
    if boutique_only:
        print(f"   ⚠️  Fields only in boutique: {boutique_only}")

    # Common fields
    common_fields = foundation_fields & boutique_fields
    print(f"   ✅ Common fields: {len(common_fields)}")
    print()

    # Align schemas - use foundation schema as base, add missing fields to boutique
    if boutique_only or foundation_only:
        print("🔧 Aligning schemas...")

        # Create unified schema (foundation schema with any boutique-only fields)
        unified_schema = foundation_schema
        for field_name in boutique_only:
            field = boutique_schema.field(field_name)
            unified_schema = unified_schema.append(field)

        # Add null columns to foundation for boutique-only fields
        if boutique_only:
            arrays = [foundation_table.column(name) for name in foundation_schema.names]
            for field_name in boutique_only:
                field = boutique_schema.field(field_name)
                # Create null array of appropriate type
                null_array = pa.nulls(foundation_count, type=field.type)
                arrays.append(null_array)
            foundation_table = pa.Table.from_arrays(arrays, schema=unified_schema)

        # Add null columns to boutique for foundation-only fields
        if foundation_only:
            arrays = [boutique_table.column(name) if name in boutique_fields
                     else pa.nulls(boutique_count, type=foundation_schema.field(name).type)
                     for name in unified_schema.names]
            boutique_table = pa.Table.from_arrays(arrays, schema=unified_schema)

        print(f"   ✅ Unified schema: {len(unified_schema.names)} fields")
        print()

    # Concatenate tables
    print("🔗 Concatenating tables...")
    combined_table = pa.concat_tables([foundation_table, boutique_table])
    combined_count = combined_table.num_rows
    print(f"   Combined rows: {combined_count:,}")

    # Verify count
    expected_count = foundation_count + boutique_count
    if combined_count != expected_count:
        print(f"   ❌ ERROR: Row count mismatch!")
        print(f"      Expected: {expected_count:,}")
        print(f"      Got:      {combined_count:,}")
        sys.exit(1)
    else:
        print(f"   ✅ Row count verified: {combined_count:,} = {foundation_count:,} + {boutique_count:,}")
    print()

    # Write combined parquet
    print(f"💾 Writing combined parquet to {output_path}...")
    pq.write_table(combined_table, output_path, compression='snappy')

    # Get file size
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"   ✅ Written: {file_size_mb:.1f} MB")
    print()

    # Summary
    print("=" * 70)
    print("✅ MERGE COMPLETE")
    print("=" * 70)
    print(f"Foundation bundle:    {foundation_count:>10,} CDEs")
    print(f"Boutique collections: {boutique_count:>10,} CDEs")
    print(f"Combined total:       {combined_count:>10,} CDEs")
    print()
    print(f"Output: {output_path}")
    print(f"Size:   {file_size_mb:.1f} MB")
    print("=" * 70)

if __name__ == "__main__":
    main()
