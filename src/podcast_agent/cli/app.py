"""Shared Typer application for Podcast-Agent commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Podcast-Agent command line interface."""
