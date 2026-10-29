import logging
import time
from pathlib import Path
from typing import Annotated

import typer
from tqdm import tqdm

from galeria.config import Settings
from galeria.core.indexer import Progress
from galeria.core.metadata import MetadataStore
from galeria.services import open_services

app = typer.Typer(help="Semantic photo & video search.", no_args_is_help=True)


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(message)s"
    )


@app.command()
def index(folder: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    """Index (or re-index) every photo and video under FOLDER. Unchanged files are skipped."""
    services = open_services()
    bar = tqdm(unit="file", desc="Indexing")

    def on_progress(p: Progress) -> None:
        bar.total = p.total
        bar.n = p.done
        bar.refresh()

    try:
        report = services.indexer.index_folder(folder, on_progress)
    finally:
        bar.close()
        services.close()

    typer.echo(
        f"added {report.added}, updated {report.updated}, removed {report.removed}, "
        f"unchanged {report.unchanged}, failed {len(report.failed)}, "
        f"vectors {report.vectors_added} — {report.seconds:.1f}s"
    )
    if report.frames_sampled:
        typer.echo(
            f"video frames: kept {report.frames_kept} of {report.frames_sampled} sampled "
            "(near-duplicates dropped)"
        )
    for path in report.failed:
        typer.echo(f"  failed: {path}", err=True)


@app.command()
def search(
    query: str,
    k: Annotated[int, typer.Option("-k", help="Number of results")] = 10,
    kind: Annotated[str | None, typer.Option("--type", help="photo or video")] = None,
    min_score: Annotated[
        float | None, typer.Option(help="Hide results below this similarity (try 0.28)")
    ] = None,
) -> None:
    """Search the index with a natural-language QUERY (any of 50+ languages)."""
    started = time.perf_counter()
    services = open_services()
    try:
        services.encoder.warmup()
        load_s = time.perf_counter() - started
        response = services.searcher.search(query, k=k, kind=kind, min_score=min_score)  # type: ignore[arg-type]
    finally:
        services.close()

    for rank, r in enumerate(response.results, start=1):
        at = f" @ {r.timestamp:.1f}s" if r.timestamp is not None else ""
        typer.echo(f"{rank:>3}. {r.score:.3f}  {r.path}{at}")
    typer.echo(
        f"{len(response.results)} results in {response.took_ms:.1f} ms "
        f"(encode {response.encode_ms:.1f} ms, search {response.search_ms:.1f} ms, "
        f"{response.total_vectors} vectors; model load {load_s:.1f}s not included)"
    )


@app.command()
def stats() -> None:
    """Show what is indexed, without loading any model."""
    settings = Settings()
    if not settings.db_path.exists():
        typer.echo("Nothing indexed yet.")
        raise typer.Exit()
    meta = MetadataStore(settings.db_path)
    try:
        counts = meta.counts()
        typer.echo(f"encoder: {meta.get_meta('encoder')}")
        typer.echo(f"roots:   {', '.join(meta.roots()) or '-'}")
        typer.echo(
            f"photos {counts['photos']}, videos {counts['videos']}, vectors {counts['vectors']}"
        )
    finally:
        meta.close()


@app.command()
def serve(
    host: Annotated[
        str, typer.Option(help="Use 0.0.0.0 to expose beyond this machine")
    ] = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Run the HTTP API (docs at /docs)."""
    import uvicorn

    uvicorn.run("galeria.api.app:app", host=host, port=port, reload=reload)
