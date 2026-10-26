"""Record a static provider snapshot audit outside Git; never qualify or install."""
import argparse
import json
from pathlib import Path
import build


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True, help="explicit effective SKSE/Plugins winning-byte snapshot")
    parser.add_argument("--out", type=Path, required=True, help="new external evidence directory")
    args = parser.parse_args(argv)
    try:
        out = build.destination(args.out)
        if args.snapshot.resolve() == out or args.snapshot.resolve() in out.parents:
            raise ValueError("Audit output cannot be inside its input snapshot")
        report = build.audit_provider(args.snapshot)
        build.verify_provider_unchanged(report)
        out.mkdir(parents=True, exist_ok=False)
        (out / "provider-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status":report["status"], "files":len(report["files"]),
                          "earTailConflicts":len(report["earTailConflicts"]), "breastConflicts":len(report["breastConflicts"]),
                          "uncertainties":len(report["uncertainties"]), "runtimeQualified":False}))
        return 0 if not (report["earTailConflicts"] or report["breastConflicts"] or report["uncertainties"]) else 2
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, "CLAW provider audit: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
