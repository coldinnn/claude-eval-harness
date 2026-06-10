"""
Generate an HTML report from eval results JSON.

Usage:
    python report.py results/results_20250101_120000.json
    python report.py results/results_20250101_120000.json --output report.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Claude Eval Report — {timestamp}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f1117;
      --surface: #1a1d27;
      --surface2: #242736;
      --border: #2d3148;
      --accent: #6c63ff;
      --green: #22c55e;
      --red: #ef4444;
      --yellow: #eab308;
      --text: #e2e8f0;
      --muted: #8892a4;
      --radius: 12px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; padding: 2rem; }}
    h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
    .stat-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.2rem;
    }}
    .stat-label {{ font-size: 0.75rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; }}
    .stat-value {{ font-size: 2rem; font-weight: 700; margin-top: 0.25rem; }}
    .stat-value.pass {{ color: var(--green); }}
    .stat-value.fail {{ color: var(--red); }}
    .stat-value.neutral {{ color: var(--text); }}
    .stat-value.accent {{ color: var(--accent); }}
    .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }}
    .chart-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.2rem;
    }}
    .chart-card h3 {{ font-size: 0.9rem; font-weight: 600; margin-bottom: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
    .chart-wrapper {{ position: relative; height: 220px; }}
    .results-section h2 {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }}
    .filter-bar {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }}
    .filter-btn {{
      padding: 0.35rem 0.8rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      color: var(--muted);
      cursor: pointer;
      font-size: 0.8rem;
      transition: all 0.15s;
    }}
    .filter-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(108,99,255,0.1); }}
    .filter-btn:hover {{ border-color: var(--accent); color: var(--text); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    thead th {{
      text-align: left;
      padding: 0.6rem 0.75rem;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
    }}
    tbody tr {{ border-bottom: 1px solid var(--border); transition: background 0.1s; }}
    tbody tr:hover {{ background: var(--surface2); }}
    td {{ padding: 0.65rem 0.75rem; vertical-align: top; }}
    .badge {{
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 600;
    }}
    .badge.pass {{ background: rgba(34,197,94,0.15); color: var(--green); }}
    .badge.fail {{ background: rgba(239,68,68,0.15); color: var(--red); }}
    .badge.partial {{ background: rgba(234,179,8,0.15); color: var(--yellow); }}
    .cat-badge {{
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.72rem;
      background: rgba(108,99,255,0.15);
      color: var(--accent);
    }}
    .diff-easy {{ color: var(--green); font-size: 0.75rem; }}
    .diff-medium {{ color: var(--yellow); font-size: 0.75rem; }}
    .diff-hard {{ color: var(--red); font-size: 0.75rem; }}
    .prompt-text {{ max-width: 320px; color: var(--muted); font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .response-text {{ max-width: 280px; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .latency {{ color: var(--muted); font-size: 0.8rem; }}
    .token-info {{ color: var(--muted); font-size: 0.75rem; }}
    .score-bar {{ display: flex; align-items: center; gap: 0.5rem; }}
    .score-num {{ font-weight: 600; min-width: 2.5rem; }}
    details summary {{ cursor: pointer; color: var(--muted); font-size: 0.8rem; }}
    details[open] summary {{ color: var(--text); }}
    details pre {{ margin-top: 0.5rem; background: var(--surface2); padding: 0.75rem; border-radius: 6px; font-size: 0.78rem; white-space: pre-wrap; word-break: break-word; max-height: 200px; overflow-y: auto; }}
    .error-text {{ color: var(--red); font-size: 0.78rem; }}
    footer {{ margin-top: 3rem; text-align: center; color: var(--muted); font-size: 0.8rem; }}
    @media (max-width: 900px) {{
      .grid-4 {{ grid-template-columns: repeat(2, 1fr); }}
      .charts-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

<h1>Claude Eval Report</h1>
<p class="subtitle">Model: <strong>{model}</strong> &nbsp;·&nbsp; Run at: {timestamp} &nbsp;·&nbsp; {total_cases} cases</p>

<div class="grid-4">
  <div class="stat-card">
    <div class="stat-label">Overall Pass Rate</div>
    <div class="stat-value {pass_color}">{pass_rate_pct}%</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Passed / Total</div>
    <div class="stat-value neutral">{passed} / {total_cases}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Avg Latency</div>
    <div class="stat-value accent">{avg_latency_ms}ms</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Cache Tokens Saved</div>
    <div class="stat-value accent">{cache_read_tokens:,}</div>
  </div>
</div>

<div class="charts-row">
  <div class="chart-card">
    <h3>Pass Rate by Category</h3>
    <div class="chart-wrapper">
      <canvas id="categoryChart"></canvas>
    </div>
  </div>
  <div class="chart-card">
    <h3>Pass Rate by Difficulty</h3>
    <div class="chart-wrapper">
      <canvas id="difficultyChart"></canvas>
    </div>
  </div>
</div>

<div class="results-section">
  <h2>All Results</h2>
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterResults('all', this)">All ({total_cases})</button>
    <button class="filter-btn" onclick="filterResults('pass', this)">✓ Passed ({passed})</button>
    <button class="filter-btn" onclick="filterResults('fail', this)">✗ Failed ({failed_plus_errors})</button>
    <button class="filter-btn" onclick="filterResults('reasoning', this)">Reasoning</button>
    <button class="filter-btn" onclick="filterResults('coding', this)">Coding</button>
    <button class="filter-btn" onclick="filterResults('safety', this)">Safety</button>
  </div>

  <table id="resultsTable">
    <thead>
      <tr>
        <th>ID</th>
        <th>Category</th>
        <th>Difficulty</th>
        <th>Prompt</th>
        <th>Response</th>
        <th>Score</th>
        <th>Latency</th>
        <th>Tokens</th>
      </tr>
    </thead>
    <tbody id="resultsBody">
      {rows}
    </tbody>
  </table>
</div>

<footer>
  Generated by <a href="https://github.com/coldin/claude-eval-harness" style="color: var(--accent);">claude-eval-harness</a>
  &nbsp;·&nbsp;
  Powered by <a href="https://www.anthropic.com" style="color: var(--accent);">Anthropic Claude</a>
</footer>

<script>
// ---------------------------------------------------------------------------
// Data for charts
// ---------------------------------------------------------------------------
const categoryData = {category_data_json};
const difficultyData = {difficulty_data_json};

// Category chart
new Chart(document.getElementById('categoryChart'), {{
  type: 'bar',
  data: {{
    labels: Object.keys(categoryData),
    datasets: [{{
      label: 'Pass Rate',
      data: Object.values(categoryData).map(v => Math.round(v * 100)),
      backgroundColor: ['rgba(108,99,255,0.7)', 'rgba(34,197,94,0.7)', 'rgba(234,179,8,0.7)', 'rgba(239,68,68,0.7)'],
      borderRadius: 6,
    }}],
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ min: 0, max: 100, ticks: {{ color: '#8892a4', callback: v => v + '%' }}, grid: {{ color: '#2d3148' }} }},
      x: {{ ticks: {{ color: '#8892a4' }}, grid: {{ display: false }} }},
    }},
  }},
}});

// Difficulty chart
new Chart(document.getElementById('difficultyChart'), {{
  type: 'doughnut',
  data: {{
    labels: Object.keys(difficultyData).map(k => k.charAt(0).toUpperCase() + k.slice(1)),
    datasets: [{{
      data: Object.values(difficultyData).map(v => Math.round(v * 100)),
      backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(234,179,8,0.7)', 'rgba(239,68,68,0.7)'],
      borderColor: ['#22c55e', '#eab308', '#ef4444'],
      borderWidth: 1,
    }}],
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'right', labels: {{ color: '#8892a4', padding: 16 }} }},
      tooltip: {{ callbacks: {{ label: ctx => ctx.label + ': ' + ctx.raw + '% pass' }} }},
    }},
  }},
}});

// ---------------------------------------------------------------------------
// Table filtering
// ---------------------------------------------------------------------------
function filterResults(filter, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const rows = document.querySelectorAll('#resultsBody tr');
  rows.forEach(row => {{
    const cat = row.dataset.category || '';
    const outcome = row.dataset.outcome || '';
    let show = false;
    if (filter === 'all') show = true;
    else if (filter === 'pass') show = outcome === 'pass';
    else if (filter === 'fail') show = outcome === 'fail';
    else show = cat === filter;
    row.style.display = show ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

ROW_TEMPLATE = """<tr data-category="{category}" data-outcome="{outcome}">
  <td><code style="font-size:0.78rem;color:#8892a4">{case_id}</code></td>
  <td><span class="cat-badge">{category}</span><br><span style="font-size:0.72rem;color:#8892a4">{subcategory}</span></td>
  <td><span class="diff-{difficulty}">{difficulty}</span></td>
  <td><details><summary class="prompt-text">{prompt_preview}</summary><pre>{prompt_full}</pre></details></td>
  <td><details><summary class="response-text">{response_preview}</summary><pre>{response_full}</pre></details></td>
  <td>
    <span class="badge {outcome_class}">{score_label}</span>
    <div style="font-size:0.75rem;color:#8892a4;margin-top:0.25rem">{score:.2f}</div>
    {error_html}
  </td>
  <td class="latency">{latency_ms:.0f}ms</td>
  <td class="token-info">in: {input_tokens}<br>out: {output_tokens}{cache_html}</td>
</tr>"""


# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------

def build_report(data: dict) -> str:
    summary = data["summary"]
    results = data["results"]

    # Category pass rates
    category_data = {
        cat: stats["pass_rate"]
        for cat, stats in summary["by_category"].items()
    }

    # Difficulty pass rates
    diff_buckets: dict[str, dict] = {}
    for r in results:
        d = r["difficulty"]
        if d not in diff_buckets:
            diff_buckets[d] = {"passed": 0, "total": 0}
        diff_buckets[d]["total"] += 1
        if r["passed"]:
            diff_buckets[d]["passed"] += 1
    difficulty_data = {
        d: round(v["passed"] / v["total"], 4)
        for d, v in diff_buckets.items()
        if v["total"] > 0
    }

    # Build rows
    rows_html = []
    for r in results:
        outcome = "pass" if r["passed"] else "fail"
        outcome_class = "pass" if r["passed"] else ("partial" if r["score"] >= 0.5 else "fail")
        score_label = "PASS" if r["passed"] else "FAIL"

        prompt_preview = (r["prompt"][:80] + "…") if len(r["prompt"]) > 80 else r["prompt"]
        response_preview = (r["response"][:80] + "…") if len(r["response"]) > 80 else r["response"]

        import html as html_lib
        error_html = (
            f'<div class="error-text">{html_lib.escape(r["error"])}</div>'
            if r.get("error") else ""
        )
        cache_html = (
            f'<br><span style="color:#6c63ff">⚡ {r["cache_read_tokens"]} cached</span>'
            if r.get("cache_read_tokens", 0) > 0 else ""
        )

        rows_html.append(ROW_TEMPLATE.format(
            case_id=r["case_id"],
            category=r["category"],
            subcategory=r["subcategory"],
            difficulty=r["difficulty"],
            prompt_preview=html_lib.escape(prompt_preview),
            prompt_full=html_lib.escape(r["prompt"]),
            response_preview=html_lib.escape(response_preview),
            response_full=html_lib.escape(r["response"]),
            score=r["score"],
            outcome=outcome,
            outcome_class=outcome_class,
            score_label=score_label,
            latency_ms=r["latency_ms"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cache_html=cache_html,
            error_html=error_html,
        ))

    total = summary["total_cases"]
    passed = summary["passed"]
    pass_rate_pct = round(summary["pass_rate"] * 100, 1)
    pass_color = "pass" if pass_rate_pct >= 80 else ("neutral" if pass_rate_pct >= 60 else "fail")
    failed_plus_errors = total - passed

    return HTML_TEMPLATE.format(
        model=summary["model"],
        timestamp=summary["timestamp"],
        total_cases=total,
        passed=passed,
        failed_plus_errors=failed_plus_errors,
        pass_rate_pct=pass_rate_pct,
        pass_color=pass_color,
        avg_latency_ms=summary.get("avg_latency_ms", "—"),
        cache_read_tokens=summary.get("total_cache_read_tokens", 0),
        rows="\n".join(rows_html),
        category_data_json=json.dumps(category_data),
        difficulty_data_json=json.dumps(difficulty_data),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate HTML eval report")
    parser.add_argument("results_json", help="Path to results JSON file")
    parser.add_argument("--output", "-o", default=None, help="Output HTML path")
    args = parser.parse_args()

    results_path = Path(args.results_json)
    if not results_path.exists():
        print(f"Error: {results_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(results_path) as f:
        data = json.load(f)

    html = build_report(data)

    out_path = args.output or results_path.with_suffix(".html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Report saved to: {out_path}")


if __name__ == "__main__":
    main()
