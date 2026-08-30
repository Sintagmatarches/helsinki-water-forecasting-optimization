from __future__ import annotations

import argparse

from .config import load_config
from .data import acquire
from .experiment import run
from .reporting import generate_figures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Helsinki water decision-science pipeline")
    parser.add_argument("command", choices=("acquire", "run", "report", "all"))
    args = parser.parse_args(argv)
    config = load_config()
    if args.command in ("acquire", "all"):
        paths = acquire(config)
        print("Acquired and curated:", *(str(path) for path in paths), sep="\n- ")
    if args.command in ("run", "all"):
        print(f"Experiment metrics: {run(config)}")
    if args.command in ("report", "all"):
        print(f"Figures: {generate_figures(config)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
