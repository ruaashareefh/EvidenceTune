"""Create cumulative v3 exclusions from the approved curated_v2 adjudication."""

import json
from collections import Counter
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    previous = root / "data/curation/squad_exclusions_v2.json"
    parent = root / "data/eval/curated_v2/squad_dev.jsonl"
    output = root / "data/curation/squad_exclusions_v3.json"
    new_exclusions = {
        "squad_v2:5ad27f01d7d075001a429745": (
            "False premise: the passage attributes the law to Newton, not "
            "Cavendish; mathematical expression is also missing"
        ),
        "squad_v2:5a5812f9770dc0001aeeffd2": (
            "Ambiguous metamorphism pathway question; pressure, temperature, "
            "space, and time form a plausible answer, making abstention unreliable"
        ),
        "squad_v2:5ad3e96b604f3c001a3ff68b": (
            "Ambiguous Frank identity and Oursel/Raimbaud leadership reference; "
            "abstention target unreliable"
        ),
    }
    newly_approved = {
        "squad_v2:5a23565482b03a001a4aa78f",
        "squad_v2:5acf9b1177cf76001a685444",
        "squad_v2:5a550e6f134fea001a0e1880",
    }
    config = json.loads(previous.read_text(encoding="utf-8"))
    records = [json.loads(line) for line in parent.read_text(encoding="utf-8").splitlines()]
    parent_ids = {r["id"] for r in records}
    approved_ids = set(config["approved_retained_ids"]) | newly_approved
    if len(records) != 20 or len(parent_ids) != 20:
        raise ValueError("Expected 20 unique parent records")
    if approved_ids | set(new_exclusions) != parent_ids or approved_ids & set(new_exclusions):
        raise ValueError("Approved decisions must partition the parent records")
    if set(new_exclusions) & set(config["excluded_ids"]):
        raise ValueError("New exclusions overlap historical exclusions")
    retained = [r for r in records if r["id"] in approved_ids]
    if Counter(r["category"] for r in retained) != {"answerable": 10, "unanswerable": 7}:
        raise ValueError("Unexpected approved category balance")
    config.update({
        "version": "3.0",
        "parent_version": "curated_v2",
        "review_status": "project_owner_approved",
        "independent_double_review": False,
        "excluded_ids": {**config["excluded_ids"], **new_exclusions},
        "approved_retained_ids": [r["id"] for r in retained],
        "false_premise_challenge_candidates": sorted(
            set(config["false_premise_challenge_candidates"])
            | {"squad_v2:5ad27f01d7d075001a429745"}
        ),
    })
    if (len(config["excluded_ids"]), len(retained),
            len(config["false_premise_challenge_candidates"])) != (19, 17, 7):
        raise ValueError("Unexpected cumulative decision counts")
    # Exclusive creation protects existing curation decisions on reruns.
    with output.open("x", encoding="utf-8") as file:
        file.write(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output.relative_to(root)}: 19 exclusions, 17 retained IDs, 7 challenge candidates")


if __name__ == "__main__":
    main()
