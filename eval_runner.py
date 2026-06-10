"""
Claude Eval Harness — async eval runner.

Runs a battery of test cases against claude-opus-4-7, scores each response,
and produces a structured JSON results file for reporting.

Usage:
    python eval_runner.py                        # run all evals
    python eval_runner.py --categories reasoning # run one category
    python eval_runner.py --limit 10             # run first 10 cases
    python eval_runner.py --concurrency 5        # parallel workers
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import anthropic
from tqdm.asyncio import tqdm_asyncio

import scorers as sc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "claude-opus-4-7"
EVALS_DIR = Path(__file__).parent / "evals"
RESULTS_DIR = Path(__file__).parent / "results"

# Shared system prompt — cached at the API level for efficiency
SYSTEM_PROMPT = (
    "You are a helpful, accurate, and honest AI assistant. "
    "Answer questions directly and concisely. "
    "When asked for a single word or number, provide only that."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EvalCase:
    id: str
    category: str
    subcategory: str
    prompt: str
    scorer: str
    difficulty: str
    notes: str = ""
    expected: Optional[str] = None
    rubric: Optional[str] = None
    expected_behavior: Optional[str] = None


@dataclass
class EvalResult:
    case_id: str
    category: str
    subcategory: str
    difficulty: str
    prompt: str
    response: str
    score: float
    passed: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    error: Optional[str] = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Load eval cases
# ---------------------------------------------------------------------------

def load_cases(categories: Optional[list[str]] = None, limit: Optional[int] = None) -> list[EvalCase]:
    cases = []
    for path in sorted(EVALS_DIR.glob("*.jsonl")):
        category = path.stem  # filename without extension
        if categories and category not in categories:
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                cases.append(EvalCase(
                    id=raw["id"],
                    category=raw["category"],
                    subcategory=raw.get("subcategory", ""),
                    prompt=raw["prompt"],
                    scorer=raw["scorer"],
                    difficulty=raw.get("difficulty", "medium"),
                    notes=raw.get("notes", ""),
                    expected=raw.get("expected"),
                    rubric=raw.get("rubric"),
                    expected_behavior=raw.get("expected_behavior"),
                ))
    if limit:
        cases = cases[:limit]
    print(f"Loaded {len(cases)} eval cases")
    return cases


# ---------------------------------------------------------------------------
# Run a single eval case
# ---------------------------------------------------------------------------

async def run_case(
    client: anthropic.AsyncAnthropic,
    semaphore: asyncio.Semaphore,
    case: EvalCase,
) -> EvalResult:
    async with semaphore:
        t0 = time.perf_counter()
        response_text = ""
        error_msg = None
        input_tokens = output_tokens = cache_read = cache_write = 0

        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": case.prompt}],
            )
            response_text = response.content[0].text
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        except anthropic.APIError as e:
            error_msg = f"API error: {e}"
            response_text = ""
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            response_text = ""

        latency_ms = (time.perf_counter() - t0) * 1000

        # Score the response (may call LLM judge — runs synchronously in the thread pool)
        if error_msg:
            score_val = 0.0
        else:
            try:
                # LLM judge is synchronous; run in executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                case_dict = {
                    "prompt": case.prompt,
                    "scorer": case.scorer,
                    "expected": case.expected,
                    "rubric": case.rubric,
                    "expected_behavior": case.expected_behavior,
                }
                score_val = await loop.run_in_executor(
                    None, sc.score, response_text, case_dict
                )
            except Exception as e:
                score_val = 0.0
                error_msg = (error_msg or "") + f" | Scoring error: {e}"

        return EvalResult(
            case_id=case.id,
            category=case.category,
            subcategory=case.subcategory,
            difficulty=case.difficulty,
            prompt=case.prompt,
            response=response_text,
            score=score_val,
            passed=score_val >= 0.5,
            latency_ms=round(latency_ms, 1),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            error=error_msg,
            notes=case.notes,
        )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_evals(
    categories: Optional[list[str]] = None,
    limit: Optional[int] = None,
    concurrency: int = 5,
    output_file: Optional[str] = None,
) -> list[EvalResult]:
    cases = load_cases(categories=categories, limit=limit)
    if not cases:
        print("No cases found. Check that evals/*.jsonl files exist.")
        return []

    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(concurrency)

    print(f"Running {len(cases)} cases with concurrency={concurrency} on {MODEL}...")
    tasks = [run_case(client, semaphore, case) for case in cases]

    results: list[EvalResult] = await tqdm_asyncio.gather(*tasks, desc="Evaluating")

    # ---------------------------------------------------------------------------
    # Summary stats
    # ---------------------------------------------------------------------------
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    errors = sum(1 for r in results if r.error)
    total_input = sum(r.input_tokens for r in results)
    total_output = sum(r.output_tokens for r in results)
    total_cache_read = sum(r.cache_read_tokens for r in results)
    avg_latency = sum(r.latency_ms for r in results) / total if total else 0

    # Per-category stats
    by_category: dict[str, dict] = {}
    for r in results:
        cat = r.category
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0}
        by_category[cat]["total"] += 1
        if r.passed:
            by_category[cat]["passed"] += 1

    summary = {
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": total,
        "passed": passed,
        "failed": total - passed - errors,
        "errors": errors,
        "pass_rate": round(passed / total, 4) if total else 0,
        "avg_latency_ms": round(avg_latency, 1),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_tokens": total_cache_read,
        "by_category": {
            cat: {
                "pass_rate": round(v["passed"] / v["total"], 4),
                "passed": v["passed"],
                "total": v["total"],
            }
            for cat, v in by_category.items()
        },
    }

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed ({summary['pass_rate']*100:.1f}%)")
    for cat, stats in summary["by_category"].items():
        print(f"  {cat:12s}  {stats['passed']}/{stats['total']}  ({stats['pass_rate']*100:.1f}%)")
    print(f"Avg latency: {avg_latency:.0f}ms | Cache savings: {total_cache_read:,} tokens")
    print("=" * 60)

    # ---------------------------------------------------------------------------
    # Persist results
    # ---------------------------------------------------------------------------
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = output_file or str(
        RESULTS_DIR / f"results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    )
    payload = {
        "summary": summary,
        "results": [asdict(r) for r in results],
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nFull results saved to: {out_path}")

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Claude Eval Harness")
    parser.add_argument(
        "--categories",
        nargs="+",
        help="Which eval categories to run (default: all)",
        choices=["reasoning", "coding", "safety"],
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of cases (for quick testing)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent API calls (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: results/results_<timestamp>.json)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_evals(
            categories=args.categories,
            limit=args.limit,
            concurrency=args.concurrency,
            output_file=args.output,
        )
    )


if __name__ == "__main__":
    main()
