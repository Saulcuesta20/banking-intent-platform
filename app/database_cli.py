from __future__ import annotations

import subprocess
from pathlib import Path

import typer


app = typer.Typer(help="Database container commands for the platform.")


def _run(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def _docker_compose_base() -> list[str]:
    return ["docker", "compose", "--profile", "optional", "-f", str(Path("docker-compose.yml"))]


@app.command("up")
def up() -> None:
    """Bring up the database containers."""
    _run(_docker_compose_base() + ["up", "-d", "neo4j", "qdrant", "postgres", "redis"])


@app.command("ps")
def ps() -> None:
    """Show database container status."""
    _run(_docker_compose_base() + ["ps", "neo4j", "qdrant", "postgres", "redis"])


@app.command("logs")
def logs(service: str = typer.Argument("neo4j", help="Service to inspect.")) -> None:
    """Print container logs for one database service."""
    _run(_docker_compose_base() + ["logs", service])


@app.command("down")
def down() -> None:
    """Stop and remove database containers."""
    _run(_docker_compose_base() + ["down"])


def main() -> None:
    app()


if __name__ == "__main__":
    main()

