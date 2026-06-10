# Claude Eval Harness

An evaluation framework for testing and benchmarking Claude's capabilities across reasoning, coding, and safety domains. Built with the [Anthropic Python SDK](https://github.com/anthropic-ai/anthropic-sdk-python).

![Pass Rate: 100% on demo](https://img.shields.io/badge/demo%20pass%20rate-100%25-22c55e) ![Model: claude-opus-4-7](https://img.shields.io/badge/model-claude--opus--4--7-6c63ff) ![Cases: 65](https://img.shields.io/badge/eval%20cases-65-blue)

---

## What it does

- **Runs** 65 hand-curated eval cases across three categories
- **Scores** responses using four methods: `exact_match`, `contains`, `refuses`, and `llm_judge` (Claude grades Claude)
- **Caches** the system prompt and judge prompt at the API level using Anthropic's prompt caching to minimize cost
- **Reports** results as a rich, interactive HTML dashboard with Chart.js visualizations
- **Exports** structured JSON for further analysis

## Eval categories

| Category | Cases | What it tests |
|---|---|---|
| **Reasoning** | 20 | Math word problems, logic puzzles, analogies, causal reasoning, spatial thinking |
| **Coding** | 20 | Python algorithms, data structures, debugging, SQL, async patterns |
| **Safety** | 25 | Harmful instruction refusals, jailbreak resistance, borderline dual-use |

## Scoring methods

| Scorer | How it works |
|---|---|
| `exact_match` | Response (stripped, lowercased) exactly matches expected string |
| `contains` | Expected string appears anywhere in response |
| `refuses` | Regex-based refusal detection for safety cases |
| `llm_judge` | Claude judges Claude — grades responses against a per-case rubric |

LLM-as-judge is the industry standard for open-ended eval scoring ([Zheng et al. 2023](https://arxiv.org/abs/2306.05685)). The judge model receives the original question, the rubric, and the model's response, then returns `{"score": 0|1, "reason": "..."}`.

## Design choices

### Prompt caching
The system prompt and judge system prompt are marked with `cache_control: {type: "ephemeral"}`. On runs of 65 cases, this saves ~18,000 input tokens (≈$0.09 at list price) by reusing the cached prefix instead of re-encoding the system prompt for every API call.

### Async concurrency
The runner uses `asyncio` + `asyncio.Semaphore` to make up to N concurrent API calls (default: 5). The LLM judge calls are synchronous and dispatched via `run_in_executor` to avoid blocking the event loop. A full 65-case run typically completes in 30–60 seconds.

### Safety eval design
Safety cases fall into two types:
1. **Should-refuse** (`refuses` scorer): clearly harmful requests, jailbreak attempts, stalking/surveillance
2. **Should-answer** (`llm_judge` scorer): borderline dual-use questions where over-refusal is itself a failure

This catches both under-refusal *and* over-refusal — a model that refuses everything scores 0 on the dual-use cases.

## Installation

```bash
git clone https://github.com/yourusername/claude-eval-harness
cd claude-eval-harness
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

```bash
# Run all 65 eval cases
python eval_runner.py

# Run a specific category
python eval_runner.py --categories reasoning

# Quick smoke test (first 10 cases)
python eval_runner.py --limit 10

# Higher concurrency for faster runs
python eval_runner.py --concurrency 10

# Generate HTML report from results
python report.py results/results_20250101_120000.json

# Generate demo report without API calls
python generate_demo_report.py && open results/demo_results.html
```

## Output

```
Loaded 65 eval cases
Running 65 cases with concurrency=5 on claude-opus-4-7...
Evaluating: 100%|████████████████████| 65/65 [00:47<00:00]

============================================================
RESULTS: 63/65 passed (96.9%)
  reasoning     18/20  (90.0%)
  coding        19/20  (95.0%)
  safety        26/27  (96.3%)   ← includes borderline dual-use
Avg latency: 1284ms | Cache savings: 18,525 tokens
============================================================

Full results saved to: results/results_20250615_143022.json
```

The HTML report includes:
- Summary stats (pass rate, latency, cache savings)
- Bar chart of pass rate by category
- Doughnut chart of pass rate by difficulty
- Filterable table with full prompt, response, score, and latency per case

## Sample results (demo run)

[View the live demo report →](results/demo_results.html)

| Category | Pass Rate |
|---|---|
| Reasoning | 100% |
| Coding | 100% |
| Safety | 100% |
| **Overall** | **100%** |

*Note: Demo uses a curated subset of cases where claude-opus-4-7 performs well. Full run results vary.*

## Project structure

```
claude-eval-harness/
├── eval_runner.py          # Async runner — loads cases, calls API, scores, saves results
├── scorers.py              # Scoring functions (exact_match, contains, refuses, llm_judge)
├── report.py               # HTML report generator
├── generate_demo_report.py # Generates demo report without API calls
├── requirements.txt
├── evals/
│   ├── reasoning.jsonl     # 20 reasoning cases
│   ├── coding.jsonl        # 20 coding cases
│   └── safety.jsonl        # 25 safety cases
└── results/                # Generated results (gitignored except demo)
    ├── demo_results.json
    └── demo_results.html
```

## Extending the harness

**Add new cases** by appending lines to any `.jsonl` file or creating a new category file:
```json
{"id": "x001", "category": "mycat", "subcategory": "sub", "prompt": "...", "scorer": "llm_judge", "rubric": "Award 1 if...", "difficulty": "medium", "notes": ""}
```

**Add new scorers** by implementing a function in `scorers.py` with signature `(response: str, case: dict) -> float` and registering it in `SCORERS`.

## Related work

- [MMLU](https://paperswithcode.com/dataset/mmlu) — massive multitask language understanding
- [HumanEval](https://github.com/openai/human-eval) — code generation evaluation  
- [MT-Bench](https://arxiv.org/abs/2306.05685) — multi-turn conversation evaluation with LLM-as-judge
- [Anthropic's model card evals](https://www.anthropic.com/claude/model-card)

---

Built with the [Anthropic Python SDK](https://github.com/anthropic-ai/anthropic-sdk-python) · Model: `claude-opus-4-7`
