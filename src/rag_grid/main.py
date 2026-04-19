"""CLI entrypoint for the RAG Grid operator copilot."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.pretty import Pretty

from rag_grid.app import cmd_ingest, cmd_index, cmd_run
from rag_grid.config import config

app = typer.Typer(
    name="rag-grid",
    help="RAG-powered operator copilot for power-grid automation.",
    add_completion=False,
)
console = Console()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


# ── ingest ─────────────────────────────────────────────────────────────────────


@app.command()
def ingest(
    docs_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing .md/.txt policy documents."),
    ] = Path("./docs"),
    chunks_file: Annotated[
        Optional[Path],
        typer.Option("--chunks-file", help="Output JSON file for chunks."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Load and chunk documents; write chunks.json for the index step."""
    _setup_logging(verbose)
    if chunks_file is None:
        chunks_file = Path(config.chunks_file)
    if not docs_dir.exists():
        console.print(f"[red]Docs directory not found:[/red] {docs_dir}")
        raise typer.Exit(1)
    cmd_ingest(docs_dir, chunks_file)


# ── index ──────────────────────────────────────────────────────────────────────


@app.command()
def index(
    chunks_file: Annotated[
        Optional[Path],
        typer.Option("--chunks-file", help="JSON file produced by 'ingest'."),
    ] = None,
    index_dir: Annotated[
        Optional[Path],
        typer.Option("--index-dir", help="Directory to write the vector index."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Build the vector index from chunks.json."""
    _setup_logging(verbose)
    if chunks_file is None:
        chunks_file = Path(config.chunks_file)
    if index_dir is None:
        index_dir = Path(config.index_dir)
    if not chunks_file.exists():
        console.print(
            f"[red]Chunks file not found:[/red] {chunks_file}\n"
            "Run 'python -m rag_grid ingest' first."
        )
        raise typer.Exit(1)
    cmd_index(chunks_file, index_dir)


# ── run ────────────────────────────────────────────────────────────────────────


@app.command()
def run(
    telemetry: Annotated[
        Path,
        typer.Option("--telemetry", help="Path to telemetry CSV file."),
    ] = Path("./data/telemetry_sample.csv"),
    goal: Annotated[
        str,
        typer.Option("--goal", help="Operator goal statement."),
    ] = "keep frequency near 60 Hz and avoid overloads",
    top_k: Annotated[
        int,
        typer.Option("--top-k", help="Number of chunks to retrieve."),
    ] = 0,
    simulate: Annotated[
        bool,
        typer.Option("--simulate/--no-simulate", help="Run toy grid simulation."),
    ] = False,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", help="Write final JSON to this file (default: stdout)."),
    ] = None,
    index_dir: Annotated[
        Optional[Path],
        typer.Option("--index-dir", help="Directory of the built vector index."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run the full RAG → plan → safety → control pipeline."""
    _setup_logging(verbose)

    if index_dir is None:
        index_dir = Path(config.index_dir)
    if top_k == 0:
        top_k = config.top_k

    mode_label = "[yellow]MOCK LLM[/yellow]" if config.mock_mode else "[green]OpenAI[/green]"
    console.print(
        Panel(
            f"[bold]RAG Grid Operator Copilot[/bold]\n"
            f"Goal: {goal}\n"
            f"Telemetry: {telemetry}\n"
            f"LLM mode: {mode_label}\n"
            f"Simulate: {simulate}",
            title="rag-grid run",
        )
    )

    if not telemetry.exists():
        console.print(f"[red]Telemetry file not found:[/red] {telemetry}")
        raise typer.Exit(1)

    result = cmd_run(
        telemetry_path=telemetry,
        goal=goal,
        index_dir=index_dir,
        top_k=top_k,
        simulate=simulate,
    )

    json_output = result.model_dump_json(indent=2)

    if output:
        output.write_text(json_output, encoding="utf-8")
        console.print(f"\n[green]✓[/green] Output written to {output}")
    else:
        console.print("\n[bold cyan]═══ FINAL OUTPUT ═══[/bold cyan]")
        console.print_json(json_output)

    # Print simulation summary if available.
    if result.simulation_result:
        sr = result.simulation_result
        console.print("\n[bold cyan]═══ SIMULATION SUMMARY ═══[/bold cyan]")
        console.print(
            f"  Frequency:  {sr.before.get('frequency_hz', '?')} Hz  →  "
            f"{sr.after.get('frequency_hz', '?')} Hz  "
            f"(Δ {sr.delta.get('frequency_hz', 0):+.4f} Hz)"
        )
        console.print(
            f"  Generation: {sr.before.get('total_gen_mw', '?')} MW  →  "
            f"{sr.after.get('total_gen_mw', '?')} MW"
        )
        console.print(
            f"  Reserve:    {sr.before.get('spinning_reserve_mw', '?')} MW  →  "
            f"{sr.after.get('spinning_reserve_mw', '?')} MW"
        )

    # Human approval reminder.
    console.print(
        "\n[bold yellow]⚠ HUMAN APPROVAL REQUIRED[/bold yellow] "
        "— CommandPlan is [red]NOT[/red] approved until an authorized operator "
        "reviews and sets human_approved=true."
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
