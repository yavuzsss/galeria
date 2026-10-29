"""Evaluate search quality on the Commons sample set.

    cd backend && uv run python ../eval/run_eval.py

Indexes samples/ into a separate data dir (incremental, so re-runs are fast), runs every query
in eval/queries.yaml and writes eval/results/latest.{md,json}.

Metrics
  P@3     share of the top 3 results that are relevant (every topic has 7+ relevant files,
          so 1.0 is reachable)
  hit@3   1 if any of the top 3 is relevant
  MRR@10  1 / rank of the first relevant result within the top 10 (0 if none)
"""

import argparse
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from galeria.config import Settings
from galeria.core.search import SearchResult
from galeria.services import open_services

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Row:
    section: str
    lang: str
    q: str
    relevant: list[str]
    top: list[dict] = field(default_factory=list)
    p3: float | None = None
    hit3: float | None = None
    rr: float | None = None
    correct: bool | None = None
    top_score: float = 0.0
    ms: float = 0.0


class Labels:
    """Maps search results back to dataset tags via the manifest."""

    def __init__(self, manifest: dict, samples: Path, audit: list[dict]):
        self.samples = samples
        self.tags: dict[str, str | None] = {
            f["path"]: f["tag"] for f in manifest["files"] if f["kind"] in ("photo", "video")
        }
        for entry in audit:  # in the index as distractors, relevant to nothing
            self.tags[entry["path"]] = None
        self.compilation = manifest["compilation"]["path"]
        self.segments = manifest["compilation"]["segments"]

    def rel_path(self, result: SearchResult) -> str:
        return Path(result.path).relative_to(self.samples).as_posix()

    def tag(self, result: SearchResult) -> str | None:
        path = self.rel_path(result)
        if path == self.compilation:
            t = result.timestamp or 0.0
            return next((s["tag"] for s in self.segments if s["start"] <= t < s["end"]), None)
        return self.tags.get(path)

    def describe(self, result: SearchResult, relevant: list[str]) -> dict:
        tag = self.tag(result)
        return {
            "path": self.rel_path(result),
            "timestamp": result.timestamp,
            "score": round(result.score, 4),
            "tag": tag,
            "relevant": tag in relevant,
        }


def run(args: argparse.Namespace) -> dict:
    samples = args.samples.resolve()
    manifest = json.loads(args.manifest.read_text())
    queries = yaml.safe_load(args.queries.read_text())
    labels = Labels(manifest, samples, yaml.safe_load(args.audit.read_text()) or [])

    services = open_services(Settings(data_dir=args.data_dir))
    services.encoder.warmup()
    # samples/compilation/ holds the photos the compilation video is made of; they must only
    # be findable through the video, so only photos/ and videos/ are indexed.
    for folder in ("photos", "videos"):
        report = services.indexer.index_folder(samples / folder)
        print(
            f"index {folder}: {report.added} added, {report.unchanged} unchanged, "
            f"{len(report.failed)} failed",
            file=sys.stderr,
        )
    search = services.searcher.search
    rows: list[Row] = []

    for q in queries["retrieval"]:
        response = search(q["q"], k=10)
        top = [labels.describe(r, q["relevant"]) for r in response.results]
        flags = [t["relevant"] for t in top]
        first = next((i for i, f in enumerate(flags) if f), None)
        rows.append(
            Row("retrieval", q["lang"], q["q"], q["relevant"], top[:3],
                p3=sum(flags[:3]) / 3, hit3=float(any(flags[:3])),
                rr=0.0 if first is None else 1 / (first + 1), correct=bool(flags and flags[0]),
                top_score=top[0]["score"] if top else 0.0, ms=response.took_ms)
        )  # fmt: skip

    for section in ("video", "moments"):
        for q in queries[section]:
            response = search(q["q"], k=3, kind="video")
            top = [labels.describe(r, q["relevant"]) for r in response.results]
            correct = bool(top) and top[0]["relevant"]
            if section == "moments":
                correct = correct and top[0]["path"] == labels.compilation
            rows.append(
                Row(section, q["lang"], q["q"], q["relevant"], top, correct=correct,
                    top_score=top[0]["score"] if top else 0.0, ms=response.took_ms)
            )  # fmt: skip

    for q in queries["negatives"]:
        response = search(q["q"], k=3)
        top = [labels.describe(r, []) for r in response.results]
        rows.append(
            Row("negatives", q["lang"], q["q"], [], top,
                top_score=top[0]["score"] if top else 0.0, ms=response.took_ms)
        )  # fmt: skip

    services.close()
    return {
        "encoder": services.encoder.name,
        "vectors": len(services.store),
        "summary": summarize(rows),
        "threshold": threshold(rows),
        "rows": [asdict(r) for r in rows],
    }


def summarize(rows: list[Row]) -> dict:
    out: dict = {}
    retrieval = [r for r in rows if r.section == "retrieval"]
    for lang in ("all", "tr", "en"):
        subset = [r for r in retrieval if lang == "all" or r.lang == lang]
        out[f"retrieval_{lang}"] = {
            "queries": len(subset),
            "p@3": statistics.mean(r.p3 for r in subset),
            "hit@3": statistics.mean(r.hit3 for r in subset),
            "mrr@10": statistics.mean(r.rr for r in subset),
        }
    for section in ("video", "moments"):
        subset = [r for r in rows if r.section == section]
        out[section] = {
            "queries": len(subset),
            "accuracy@1": statistics.mean(r.correct for r in subset),
        }
    ms = sorted(r.ms for r in rows)
    out["latency_ms"] = {"median": statistics.median(ms), "p95": ms[int(0.95 * (len(ms) - 1))]}
    return out


def threshold(rows: list[Row]) -> dict:
    """Best cutoff separating 'top hit is right' from 'nothing should match'.

    Positives: top-1 scores of retrieval queries whose top result is relevant.
    Negatives: top-1 scores of the negative queries.
    """
    pos = sorted(r.top_score for r in rows if r.section == "retrieval" and r.correct)
    neg = sorted(r.top_score for r in rows if r.section == "negatives")
    candidates = sorted(set(pos + neg))
    best = max(
        candidates,
        key=lambda t: (
            (sum(p >= t for p in pos) / len(pos) + sum(n < t for n in neg) / len(neg)) / 2
        ),
    )
    return {
        "suggested": best,
        "positives_kept": sum(p >= best for p in pos) / len(pos),
        "negatives_hidden": sum(n < best for n in neg) / len(neg),
        "positive_scores": {"min": pos[0], "median": statistics.median(pos), "max": pos[-1]},
        "negative_scores": {"min": neg[0], "median": statistics.median(neg), "max": neg[-1]},
    }


def markdown(result: dict) -> str:
    s, t = result["summary"], result["threshold"]
    lines = [
        "# Eval results",
        "",
        f"Encoder `{result['encoder']}`, {result['vectors']} vectors.",
        "",
        "## Retrieval (20 topics, Turkish + English)",
        "",
        "| Queries | P@3 | hit@3 | MRR@10 |",
        "|---|---|---|---|",
    ]
    for lang, label in (("all", "All"), ("tr", "Turkish"), ("en", "English")):
        m = s[f"retrieval_{lang}"]
        lines.append(
            f"| {label} ({m['queries']}) | {m['p@3']:.3f} | {m['hit@3']:.3f} | {m['mrr@10']:.3f} |"
        )
    lines += [
        "",
        "## Video",
        "",
        f"- Right video first: {s['video']['accuracy@1']:.0%} of {s['video']['queries']} queries",
        f"- Right moment in the compilation video: {s['moments']['accuracy@1']:.0%} of "
        f"{s['moments']['queries']} queries",
        "",
        "## Latency",
        "",
        f"Median {s['latency_ms']['median']:.1f} ms, p95 {s['latency_ms']['p95']:.1f} ms per query "
        "(text encoding + FAISS search + metadata).",
        "",
        "## Score threshold",
        "",
        f"Top-1 scores of answered queries: {t['positive_scores']['min']:.3f}–"
        f"{t['positive_scores']['max']:.3f} (median {t['positive_scores']['median']:.3f}); "
        f"of queries with no match: {t['negative_scores']['min']:.3f}–"
        f"{t['negative_scores']['max']:.3f}.",
        f"A cutoff at {t['suggested']:.3f} keeps {t['positives_kept']:.0%} of correct top hits and "
        f"hides {t['negatives_hidden']:.0%} of no-match queries.",
        "",
        "## Per query",
        "",
        "| | Lang | Query | P@3 | Top 3 (✓ relevant) |",
        "|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        mark = {True: "✓", False: "✗", None: ""}[r["correct"]]
        p3 = "" if r["p3"] is None else f"{r['p3']:.2f}"
        top = ", ".join(
            f"{'✓' if x['relevant'] else '·'} {x['tag'] or Path(x['path']).name}"
            + (f"@{x['timestamp']:.0f}s" if x["timestamp"] is not None else "")
            for x in r["top"]
        )
        lines.append(f"| {r['section']} {mark} | {r['lang']} | {r['q']} | {p3} | {top} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", type=Path, default=ROOT / "samples")
    parser.add_argument("--manifest", type=Path, default=ROOT / "scripts" / "samples_manifest.json")
    parser.add_argument("--queries", type=Path, default=ROOT / "eval" / "queries.yaml")
    parser.add_argument("--audit", type=Path, default=ROOT / "eval" / "label_audit.yaml")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "eval")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    args = parser.parse_args()

    result = run(args)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    text = markdown(result)
    (args.out / "latest.md").write_text(text)
    print(text.split("## Per query")[0])


if __name__ == "__main__":
    main()
