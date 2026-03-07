#!/usr/bin/env python3
"""CLI tool to locate README.md by question ID."""

import argparse
from pathlib import Path


def locate_pool_dir(
    start: Path | None = None,
    max_iterations: int = 5,
) -> Path | None:
    """
    Locate the 'pool' directory starting from the given path.
    First checks if 'pool' exists in current directory, then traverses up.
    """
    current = (start or Path.cwd()).resolve()

    for _ in range(max_iterations):
        pool_path = current / "pool"
        if pool_path.is_dir():
            return pool_path

        parent = current.parent
        if parent == current:  # reached root
            break
        current = parent

    return None


def find_readme_by_id(question_id: str, pool_dir: Path | None = None) -> Path | None:
    """
    Find README.md for the given question ID (e.g., 'J-02-01').
    Walks through pool directory to find a folder starting with the ID.
    """
    if pool_dir is None:
        pool_dir = locate_pool_dir()

    if pool_dir is None:
        return None

    # Walk through pool directory
    for readme in pool_dir.rglob("README.md"):
        # Check if parent directory starts with the question ID
        if readme.parent.name.startswith(question_id):
            return readme

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Locate README.md by question ID")
    parser.add_argument(
        "--id",
        required=True,
        help="Question ID (e.g., J-02-01, M-04-02, S-01-03)",
    )
    args = parser.parse_args()

    readme_path = find_readme_by_id(args.id)

    if readme_path:
        print(readme_path)
    else:
        print(f"README not found for ID: {args.id}", file=__import__("sys").stderr)
        exit(1)


if __name__ == "__main__":
    main()
