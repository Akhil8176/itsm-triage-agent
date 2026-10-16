"""Blind human audit of evaluation results.

1. Make an audit sheet (ticket text only, no labels shown):
     python3 audit.py make --results eval_300.jsonl --csv tickets.csv --n 50
   Fill in the your_* columns in audit.csv (Numbers / Excel / any editor).

2. Score it: who do you agree with more, the dataset or the model?
     python3 audit.py score

3. See how each field goes wrong (rows = dataset label, columns = model):
     python3 audit.py confusion --results eval_300.jsonl
"""
import argparse
import csv
import json
import random
from collections import Counter, defaultdict

FIELDS = ("TYPE", "PRIORITY", "ASSIGNMENT GROUP")
COL = {"TYPE": "your_type", "PRIORITY": "your_priority", "ASSIGNMENT GROUP": "your_group"}


def load_results(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def make(args):
    results = load_results(args.results)
    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_title = {}
    for r in rows:
        subject = (r.get("subject") or "").strip()
        body = (r.get("body") or "").strip()
        by_title.setdefault(subject or body[:80], body)

    picked = random.Random(args.seed).sample(results, min(args.n, len(results)))
    options = defaultdict(set)
    for r in results:
        for f in FIELDS:
            options[f].add(r["truth"][f])

    key = []
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "subject", "body"] + [COL[x] for x in FIELDS])
        for i, r in enumerate(picked, 1):
            w.writerow([i, r["title"], by_title.get(r["title"], "")] + [""] * len(FIELDS))
            key.append({"id": i, "truth": r["truth"], "decision": r["decision"], "confident": r["confident"]})
    with open(args.key, "w") as f:
        json.dump(key, f, indent=1)

    print(f"Wrote {args.out} ({len(picked)} tickets). Labels are hidden in {args.key}; don't open it until you're done.")
    print("Use exactly one of these values in each column:")
    for fld in FIELDS:
        print(f"  {COL[fld]}: {', '.join(sorted(options[fld]))}")


def score(args):
    key = {k["id"]: k for k in json.load(open(args.key))}
    with open(args.out, newline="", encoding="utf-8") as f:
        sheet = list(csv.DictReader(f))

    print(f"{'Field':<18}{'Rated':>6}{'You = dataset':>16}{'You = model':>14}{'Dataset = model':>18}")
    for fld in FIELDS:
        n = you_data = you_model = data_model = 0
        for row in sheet:
            mine = (row.get(COL[fld]) or "").strip().lower()
            if not mine:
                continue
            k = key[int(row["id"])]
            truth = k["truth"][fld].lower()
            model = (k["decision"].get(fld) or "").lower()
            n += 1
            you_data += mine == truth
            you_model += mine == model
            data_model += truth == model
        if n:
            print(f"{fld:<18}{n:>6}{you_data / n:>16.0%}{you_model / n:>14.0%}{data_model / n:>18.0%}")
    print("\nIf you agree with the model more often than with the dataset, the labels are the weak link.")


def confusion(args):
    results = load_results(args.results)
    for fld in FIELDS:
        grid = Counter((r["truth"][fld], r["decision"].get(fld, "")) for r in results)
        labels = sorted({t for t, _ in grid} | {m for _, m in grid if m})
        width = max(len(x) for x in labels) + 2
        print(f"\n{fld}  (rows = dataset label, columns = model answer)")
        print(" " * width + "".join(f"{x[:12]:>14}" for x in labels))
        for t in labels:
            print(f"{t:<{width}}" + "".join(f"{grid[(t, m)]:>14}" for m in labels))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--results", default="eval_300.jsonl")
    m.add_argument("--csv", default="tickets.csv")
    m.add_argument("--n", type=int, default=50)
    m.add_argument("--seed", type=int, default=7)
    for p in (m, sub.add_parser("score")):
        p.add_argument("--out", default="audit.csv")
        p.add_argument("--key", default="audit_key.json")
    c = sub.add_parser("confusion")
    c.add_argument("--results", default="eval_300.jsonl")
    args = ap.parse_args()
    {"make": make, "score": score, "confusion": confusion}[args.cmd](args)


if __name__ == "__main__":
    main()
