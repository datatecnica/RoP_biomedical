"""Command-line interface for RoP.

    rop init        Set up the RoP schema in a Forge database
    rop validate    Validate a candidate CDE collection against the contract
    rop bundle      Build a distributable bundle from a database or JSON
    rop info        Print info about a bundle or anchor registry
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from rop.anchors import load_anchors, DEFAULT_ANCHOR_DIR
from rop.schema import RoPElement
from rop.validate import (
    CollectionContext,
    Severity,
    parse_priority_rule,
    validate_collection,
)


console = Console()


@click.group()
@click.version_option()
def main() -> None:
    """RoP — Biomedical Reference of Parameters."""


# ---------------------------------------------------------------------------
# rop info
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--anchors-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_ANCHOR_DIR,
    help="Directory containing anchor tier JSON files.",
)
def info(anchors_dir: Path) -> None:
    """Print summary info about the anchor registry."""
    registry = load_anchors(anchors_dir)

    table = Table(title=f"RoP Anchor Registry ({len(registry)} anchors)")
    table.add_column("Tier", style="cyan", no_wrap=True)
    table.add_column("Item", style="green")
    table.add_column("Priority", style="yellow")
    table.add_column("Type", style="magenta")

    for tier_name, items in registry.by_tier.items():
        for anchor in items:
            table.add_row(
                tier_name,
                anchor.item,
                anchor.priority or "—",
                anchor.item_type or "—",
            )

    console.print(table)


# ---------------------------------------------------------------------------
# rop validate
# ---------------------------------------------------------------------------

@main.command()
@click.argument(
    "collection_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--longitudinal/--no-longitudinal",
    default=False,
    help="Treat the submission as a longitudinal cohort.",
)
@click.option(
    "--genetic-cohort/--no-genetic-cohort",
    default=False,
    help="Treat the submission as a genetic cohort.",
)
@click.option(
    "--cross-cohort/--no-cross-cohort",
    default=False,
    help="Submission federates across multiple cohorts (triggers IndividualAliases recommendation).",
)
@click.option(
    "--biosamples/--no-biosamples",
    default=False,
    help="Submission contains biosamples.",
)
@click.option(
    "--omics-data/--no-omics-data",
    default=False,
    help="Submission contains omics measurements.",
)
@click.option(
    "--sharing-ready/--no-sharing-ready",
    default=False,
    help="Require Tier 7 (Governance) for re-distribution eligibility.",
)
@click.option(
    "--anchors-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_ANCHOR_DIR,
)
def validate(
    collection_path: Path,
    longitudinal: bool,
    genetic_cohort: bool,
    cross_cohort: bool,
    biosamples: bool,
    omics_data: bool,
    sharing_ready: bool,
    anchors_dir: Path,
) -> None:
    """Validate a collection JSON against the RoP contract."""
    with collection_path.open() as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        console.print("[red]Collection JSON must be an array of element objects[/red]")
        sys.exit(1)

    elements: list[RoPElement] = []
    for entry in raw:
        try:
            elements.append(RoPElement(**entry))
        except Exception as exc:
            console.print(
                f"[red]Failed to parse element '{entry.get('item', '?')}': {exc}[/red]"
            )
            sys.exit(1)

    populated = {e.item for e in elements}
    field_values = {e.item: e.values for e in elements}

    context = CollectionContext(
        populated_fields=populated,
        field_values=field_values,
        is_longitudinal=longitudinal,
        is_genetic_cohort=genetic_cohort,
        is_cross_cohort=cross_cohort,
        has_biosamples=biosamples,
        has_omics_data=omics_data,
        requires_sharing_ready=sharing_ready,
    )

    registry = load_anchors(anchors_dir)
    result = validate_collection(elements, context, registry)

    _print_validation_result(result)
    if not result.ok:
        sys.exit(1)


def _print_validation_result(result) -> None:
    if result.errors:
        console.print(f"\n[red bold]✗ Errors ({len(result.errors)})[/red bold]")
        for err in result.errors:
            console.print(f"  [red]●[/red] [{err.code}] {err.message}")
            if err.item:
                console.print(f"    item: {err.item}")
    if result.warnings:
        console.print(f"\n[yellow bold]⚠ Warnings ({len(result.warnings)})[/yellow bold]")
        for w in result.warnings:
            console.print(f"  [yellow]●[/yellow] [{w.code}] {w.message}")
    if result.info:
        console.print(f"\n[blue bold]ℹ Info ({len(result.info)})[/blue bold]")
        for i in result.info:
            console.print(f"  [blue]●[/blue] [{i.code}] {i.message}")
    if result.ok and not result.warnings:
        console.print("\n[green bold]✓ Validation passed[/green bold]")
    elif result.ok:
        console.print("\n[green]✓ No errors (warnings present)[/green]")


# ---------------------------------------------------------------------------
# rop parse-priority — helper to test the conditional-required parser
# ---------------------------------------------------------------------------

@main.command("parse-priority")
@click.argument("priority_string")
def parse_priority(priority_string: str) -> None:
    """Show how a priority string is parsed by the validation engine."""
    rule = parse_priority_rule(priority_string)
    console.print({
        "raw": rule.raw,
        "kind": rule.kind.value,
        "field_name": rule.field_name,
        "field_value": rule.field_value,
        "context": rule.context,
    })


# ---------------------------------------------------------------------------
# rop bundle (skeleton — wire to rop.bundle.build_bundle once ingest lands)
# ---------------------------------------------------------------------------

@main.command()
@click.option("--source", required=True, help="Path to elements JSON or DuckDB file")
@click.option("--version", required=True, help='Bundle version (e.g., "2026.04")')
@click.option("--out", required=True, type=click.Path(path_type=Path), help="Output directory")
def bundle(source: str, version: str, out: Path) -> None:
    """Build a distributable RoP bundle."""
    from rop.bundle import build_bundle as _build

    src = Path(source)
    if not src.exists():
        console.print(f"[red]Source not found: {src}[/red]")
        sys.exit(1)

    if src.suffix == ".json":
        with src.open() as f:
            raw = json.load(f)
        elements = [RoPElement(**entry) for entry in raw]
    else:
        console.print("[red]Only JSON sources supported in v0.1; DuckDB ingest in v0.2[/red]")
        sys.exit(2)

    out.mkdir(parents=True, exist_ok=True)
    bundle_dir = _build(elements, out_dir=out, bundle_version=version)
    console.print(f"[green]✓ Bundle written to {bundle_dir}[/green]")


if __name__ == "__main__":
    main()
