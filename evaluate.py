"""Measure triage accuracy and whether self-disagreement predicts mistakes.

Runs labeled tickets through the triage and reports:
  - accuracy per field
  - how many tickets the model was confident about vs. flagged
  - accuracy of the confident group vs. the flagged group

Example:
  python3 evaluate.py --csv tickets.csv \
      --text-cols subject,body \
      --label "CATEGORY=queue" --label "PRIORITY=priority" \
      --n 300
"""
import argparse
import csv
import json
import random
from concurrent.futures import ThreadPoolExecutor

from triage import MODEL, triage_with_confidence


def load(path, text_cols, labels, n, seed, filters):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for col, value in filters:
        rows = [r for r in rows if (r.get(col) or "").strip() == value]
    rows = [r for r in rows if all((r.get(c) or "").strip() for c in labels.values())]
    taxonomy = {field: sorted({r[c].strip() for r in rows}) for field, c in labels.items()}
    random.Random(seed).shuffle(rows)
    rows = rows[:n]
    tickets = []
    for r in rows:
        title = (r.get(text_cols[0]) or "").strip()
        body = " ".join((r.get(c) or "").strip() for c in text_cols[1:])
        tickets.append({
            "title": title or body[:80],
            "description": body or title,
            "truth": {field: r[c].strip() for field, c in labels.items()},
        })
    return tickets, taxonomy


def pct(a, b):
    return f"{a / b:.1%}" if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--text-cols", default="subject,body")
    ap.add_argument("--label", action="append", required=True, help="FIELD=column, e.g. CATEGORY=queue")
    ap.add_argument("--filter", action="append", default=[], help="column=value, e.g. language=en")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="eval_results")
    args = ap.parse_args()

    labels = dict(x.split("=", 1) for x in args.label)
    filters = [tuple(x.split("=", 1)) for x in args.filter]
    tickets, taxonomy = load(args.csv, args.text_cols.split(","), labels, args.n, args.seed, filters)
    print(f"Model: {MODEL} | {len(tickets)} tickets | {args.samples} samples each")
    for field, options in taxonomy.items():
        print(f"  {field}: {len(options)} options")

    def run(t):
        try:
            res = triage_with_confidence(t["title"], t["description"], taxonomy, samples=args.samples)
        except Exception as exc:
            return t, None, str(exc)
        return t, res, None

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, (t, res, err) in enumerate(pool.map(run, tickets), 1):
            results.append((t, res, err))
            if i % 25 == 0:
                print(f"  {i}/{len(tickets)} done")

    ok = [(t, r) for t, r, e in results if r]
    errors = len(results) - len(ok)
    fields = list(labels)

    def correct(t, r, field):
        return r["decision"].get(field, "").lower() == t["truth"][field].lower()

    lines = [f"# Triage evaluation ({MODEL}, {args.samples} samples, {len(ok)} tickets)", ""]
    lines.append("| Group | Tickets | " + " | ".join(f"{f} accuracy" for f in fields) + " | All fields right |")
    lines.append("|---|---|" + "---|" * (len(fields) + 1))
    for name, group in (
        ("All", ok),
        ("Confident (all samples agreed)", [(t, r) for t, r in ok if r["confident"]]),
        ("Flagged (samples disagreed)", [(t, r) for t, r in ok if not r["confident"]]),
    ):
        accs = [pct(sum(correct(t, r, f) for t, r in group), len(group)) for f in fields]
        allr = pct(sum(all(correct(t, r, f) for f in fields) for t, r in group), len(group))
        lines.append(f"| {name} | {len(group)} | " + " | ".join(accs) + f" | {allr} |")

    wrong = [(t, r) for t, r in ok if not all(correct(t, r, f) for f in fields)]
    caught = sum(1 for t, r in wrong if not r["confident"])
    tokens = sum(r["tokens"] for t, r in ok)
    lines += [
        "",
        f"- Flagged for review: {pct(sum(not r['confident'] for t, r in ok), len(ok))} of tickets",
        f"- Mistakes caught by the flag: {caught} of {len(wrong)} ({pct(caught, len(wrong))})",
        f"- Tokens used: {tokens:,}",
        f"- Errors: {errors}",
    ]
    summary = "\n".join(lines)
    print("\n" + summary)

    with open(f"{args.out}.md", "w") as f:
        f.write(summary + "\n")
    with open(f"{args.out}.jsonl", "w") as f:
        for t, r in ok:
            f.write(json.dumps({
                "title": t["title"], "truth": t["truth"], "decision": r["decision"],
                "agreement": r["agreement"], "confident": r["confident"],
            }) + "\n")
    print(f"\nSaved {args.out}.md and {args.out}.jsonl")


if __name__ == "__main__":
    main()
