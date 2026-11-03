"""CLI: python -m ghostlab run <clip> | scoreboard <truth.csv>"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ghostlab import meta_api, pipeline
from ghostlab.fit.select import MODULES


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="ghostlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("clip", type=Path)
    r.add_argument("--out", type=Path, default=Path("result.json"))
    r.add_argument("--work", type=Path, default=Path("work"))
    r.add_argument("--object")
    r.add_argument("--size", type=float)
    r.add_argument("--motion", choices=sorted(MODULES))
    s = sub.add_parser("scoreboard")
    s.add_argument("truth", type=Path)
    s.add_argument("--out", type=Path, default=Path("docs/scoreboard.md"))
    args = ap.parse_args(argv)
    try:
        c = meta_api.client()
    except meta_api.MissingKeyError as exc:
        raise SystemExit(str(exc))
    if args.cmd == "run":
        overrides = pipeline.Overrides(args.object, args.size, args.motion)
        result = pipeline.run(args.clip, args.work, c, overrides)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        fit = result.get("fits", {}).get(result.get("chosen"), result)
        print(json.dumps({"chosen": result.get("chosen"), "fit": fit, "warnings": result.get("warnings")}, indent=2))
    else:
        from ghostlab import scoreboard

        def run_one(clip: Path, motion: str) -> dict:
            return pipeline.run(clip, Path("work") / clip.stem, c, pipeline.Overrides(motion=motion))

        scoreboard.write(args.truth, args.out, run_one)
        print(args.out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
