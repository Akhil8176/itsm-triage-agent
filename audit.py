"""Blind human audit of evaluation results.

1. Make an audit sheet (ticket text only, no labels shown):
     python3 audit.py make --results eval_300.jsonl --csv tickets.csv --n 50
   Then label them in the Terminal, one ticket at a time:
     python3 audit.py label

2. Score it: who do you agree with more, the dataset or the model?
     python3 audit.py score

3. Second rater: give them a blind subset of the same tickets, then compare.
     python3 audit.py rater2 --n 20
     python3 audit.py label --out audit_rater2.csv
     python3 audit.py agree

4. See how each field goes wrong (rows = dataset label, columns = model):
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


GUIDE = {
    "TYPE": {
        "Incident": "something is broken or degraded",
        "Request": "asking for something (access, info, a new service)",
        "Problem": "a recurring issue or root cause behind several incidents",
        "Change": "asking to modify, upgrade, or reconfigure something",
    },
    "PRIORITY": {
        "high": "business-critical, many users affected, or work fully blocked",
        "medium": "impaired, but there is a workaround",
        "low": "minor, cosmetic, or a general question",
    },
}


def _options(results_path):
    opts = defaultdict(set)
    for r in load_results(results_path):
        for f in FIELDS:
            opts[f].add(r["truth"][f])
    return {f: sorted(v) for f, v in opts.items()}


def _save(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def label(args):
    import os
    import textwrap

    options = _options(args.results)
    with open(args.out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    todo = [r for r in rows if not all((r.get(COL[f]) or "").strip() for f in FIELDS)]
    done = len(rows) - len(todo)

    for row in todo:
        os.system("clear")
        done_now = sum(all((r.get(COL[f]) or "").strip() for f in FIELDS) for r in rows)
        print(f"Ticket {done_now + 1} of {len(rows)}   (type q to save and quit)\n")
        print("SUBJECT:", row["subject"] or "(none)")
        print("\n" + textwrap.fill(row["body"] or "(no body)", 100) + "\n")
        for fld in FIELDS:
            print(f"-- {fld} --")
            for i, opt in enumerate(options[fld], 1):
                hint = GUIDE.get(fld, {}).get(opt, "")
                print(f"  {i}. {opt}" + (f"  ({hint})" if hint else ""))
            while True:
                choice = input("Your pick: ").strip().lower()
                if choice == "q":
                    _save(args.out, rows)
                    print(f"\nSaved. Run 'python3 audit.py label' to continue.")
                    return
                if choice.isdigit() and 1 <= int(choice) <= len(options[fld]):
                    row[COL[fld]] = options[fld][int(choice) - 1]
                    break
                print(f"  Type a number from 1 to {len(options[fld])}, or q.")
            print()
        _save(args.out, rows)

    print(f"All {len(rows)} tickets labeled. Now run: python3 audit.py score")


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


def _rated(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {int(r["id"]): r for r in rows if all((r.get(COL[f]) or "").strip() for f in FIELDS)}


def rater2(args):
    first = _rated(args.source)
    ids = sorted(random.Random(args.seed).sample(sorted(first), min(args.n, len(first))))
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "subject", "body"] + [COL[x] for x in FIELDS])
        for i in ids:
            r = first[i]
            w.writerow([i, r["subject"], r["body"]] + [""] * len(FIELDS))
    print(f"Wrote {args.out} with {len(ids)} tickets for the second rater (no answers included).")
    print(f"They label with: python3 audit.py label --out {args.out}")


def _kappa(pairs):
    """Cohen's kappa: agreement corrected for chance."""
    n = len(pairs)
    if not n:
        return float("nan")
    observed = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def agree(args):
    key = {k["id"]: k for k in json.load(open(args.key))}
    a, b = _rated(args.a), _rated(args.b)
    ids = sorted(set(a) & set(b))
    print(f"Tickets labeled by both raters: {len(ids)}\n")
    print(f"{'Field':<18}{'R1 = R2':>9}{'kappa':>8}{'R1 = data':>11}{'R2 = data':>11}{'R1 = model':>12}{'R2 = model':>12}")
    for fld in FIELDS:
        col = COL[fld]
        r1 = [a[i][col].strip().lower() for i in ids]
        r2 = [b[i][col].strip().lower() for i in ids]
        data = [key[i]["truth"][fld].lower() for i in ids]
        model = [(key[i]["decision"].get(fld) or "").lower() for i in ids]

        def pct(x, y):
            return sum(p == q for p, q in zip(x, y)) / len(ids) if ids else 0

        print(f"{fld:<18}{pct(r1, r2):>9.0%}{_kappa(list(zip(r1, r2))):>8.2f}{pct(r1, data):>11.0%}"
              f"{pct(r2, data):>11.0%}{pct(r1, model):>12.0%}{pct(r2, model):>12.0%}")
    print("\nR1 = R2 is the human ceiling: how often two people agree with each other.")
    print("kappa: 0 = chance, 0.4-0.6 moderate, 0.6-0.8 substantial, 0.8+ near-perfect.")


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
    lab = sub.add_parser("label")
    lab.add_argument("--results", default="eval_300.jsonl")
    for p in (m, sub.add_parser("score"), lab):
        p.add_argument("--out", default="audit.csv")
        p.add_argument("--key", default="audit_key.json")
    r2 = sub.add_parser("rater2")
    r2.add_argument("--source", default="audit_clean.csv")
    r2.add_argument("--n", type=int, default=20)
    r2.add_argument("--seed", type=int, default=11)
    r2.add_argument("--out", default="audit_rater2.csv")
    ag = sub.add_parser("agree")
    ag.add_argument("--a", default="audit_clean.csv")
    ag.add_argument("--b", default="audit_rater2.csv")
    ag.add_argument("--key", default="audit_key.json")
    c = sub.add_parser("confusion")
    c.add_argument("--results", default="eval_300.jsonl")
    args = ap.parse_args()
    {"make": make, "label": label, "score": score, "rater2": rater2, "agree": agree, "confusion": confusion}[args.cmd](args)


if __name__ == "__main__":
    main()
