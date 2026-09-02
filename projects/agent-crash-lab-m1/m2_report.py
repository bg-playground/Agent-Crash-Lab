from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

from m2_evidence import assert_secret_free_text, validate_evidence_file

HERE = Path(__file__).resolve().parent
DEFAULT_EVIDENCE = HERE / "evidence" / "m1c_characterization.json"
DEFAULT_OUTPUT = HERE / "evidence" / "m1c_report.html"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def display(value: Any) -> str:
    if value is None or value == "unavailable":
        return "Unavailable — not retained"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return " → ".join(str(item) for item in value) if value else "None recorded"
    if isinstance(value, dict):
        return ", ".join(f"{key}={val}" for key, val in value.items())
    return str(value)


def render_report(data: dict[str, Any]) -> str:
    experiment = data["experiment"]
    oracle = data["oracle"]
    replay = data["replay_contract"]
    trials = data["trials"]
    failures = experiment["failure_classes"]
    wilson = experiment["failure_probability_wilson_95"]

    trial_cells = []
    trial_rows = []
    for trial in trials:
        outcome = trial["objective_outcome"]
        css_class = "pass" if outcome == "PASS" else "fail" if outcome == "FAIL" else "unknown"
        trial_cells.append(
            f'<div class="trial {css_class}" title="Trial {trial["ordinal"]}: {esc(display(outcome))}">'
            f'{trial["ordinal"]}</div>'
        )
        trial_rows.append(
            "<tr>"
            f'<td>{trial["ordinal"]}</td>'
            f'<td>{esc(trial["perturbation"])}</td>'
            f'<td>{esc(display(trial["run_fingerprint"]))}</td>'
            f'<td>{esc(display(outcome))}</td>'
            f'<td>{esc(display(trial["failure_class"]))}</td>'
            f'<td>{esc(display(trial["final_state"]))}</td>'
            f'<td>{esc(display(trial["events"]))}</td>'
            f'<td>{esc(display(trial["replay_available"]))}</td>'
            f'<td>{esc(display(trial["agent_browser_error_status"]))}</td>'
            f'<td>{esc(trial["retention_status"])}</td>'
            "</tr>"
        )

    failure_items = "".join(
        f"<li><code>{esc(name)}</code>: {count}</li>" for name, count in sorted(failures.items())
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Crash Lab — M1C Evidence Report</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 80px; line-height: 1.5; }}
h1 {{ font-size: clamp(2rem, 5vw, 4rem); margin-bottom: .2em; }}
h2 {{ margin-top: 2.2em; }}
.lede {{ font-size: 1.2rem; max-width: 850px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 12px; margin: 28px 0; }}
.card {{ border: 1px solid #8886; border-radius: 12px; padding: 18px; }}
.big {{ font-size: 2rem; font-weight: 750; display: block; }}
.trials {{ display: grid; grid-template-columns: repeat(20,minmax(30px,1fr)); gap: 5px; margin: 18px 0; }}
.trial {{ border-radius: 6px; text-align: center; padding: 8px 2px; font-weight: 700; border: 1px solid #8886; }}
.pass {{ background: color-mix(in srgb, green 25%, transparent); }}
.fail {{ background: color-mix(in srgb, red 28%, transparent); }}
.unknown {{ background: color-mix(in srgb, gray 20%, transparent); }}
.note {{ border-left: 4px solid currentColor; padding: 10px 16px; opacity: .88; }}
table {{ border-collapse: collapse; width: max-content; min-width: 1900px; font-size: .86rem; table-layout: auto; }}
th, td {{ border-bottom: 1px solid #8885; padding: 9px 10px; text-align: left; vertical-align: top; overflow-wrap: normal; word-break: normal; }}
th {{ position: sticky; top: 0; background: Canvas; white-space: nowrap; }}
th:nth-child(1), td:nth-child(1) {{ min-width: 52px; }}
th:nth-child(2), td:nth-child(2) {{ min-width: 140px; }}
th:nth-child(3), td:nth-child(3) {{ min-width: 165px; }}
th:nth-child(4), td:nth-child(4) {{ min-width: 105px; white-space: nowrap; }}
th:nth-child(5), td:nth-child(5) {{ min-width: 155px; }}
th:nth-child(6), td:nth-child(6) {{ min-width: 255px; }}
th:nth-child(7), td:nth-child(7) {{ min-width: 650px; }}
th:nth-child(8), td:nth-child(8) {{ min-width: 90px; white-space: nowrap; }}
th:nth-child(9), td:nth-child(9) {{ min-width: 270px; }}
th:nth-child(10), td:nth-child(10) {{ min-width: 160px; white-space: nowrap; }}
.table-wrap {{ overflow-x: auto; padding-bottom: 8px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
footer {{ margin-top: 50px; opacity: .72; }}
</style>
</head>
<body>
<header>
<p><strong>Agent Crash Lab / M2 evidence package</strong></p>
<h1>Same agent. Same task. Same rollback. Different outcomes.</h1>
<p class="lede">The same autonomous agent, given the same task and the same deterministic <code>{esc(experiment['condition'])}</code> perturbation, recovered in {experiment['recoveries']} of {experiment['valid_trials']} valid runs and failed in {experiment['failures']} of {experiment['valid_trials']}.</p>
</header>

<section class="cards" aria-label="Characterization summary">
<div class="card"><span class="big">{experiment['recoveries']}/{experiment['valid_trials']}</span>recoveries</div>
<div class="card"><span class="big">{experiment['failures']}/{experiment['valid_trials']}</span>objective failures</div>
<div class="card"><span class="big">{pct(experiment['recovery_rate'])}</span>observed recovery rate</div>
<div class="card"><span class="big">{pct(experiment['failure_rate'])}</span>observed failure rate</div>
</section>

<section>
<h2>What the experiment established</h2>
<p>Model <code>{esc(experiment['model'])}</code> was evaluated for exactly {experiment['valid_trials']} valid trials under the frozen <code>{esc(experiment['condition'])}</code> condition. There were {experiment['invalid_infrastructure_attempts']} infrastructure-invalid attempts in the canonical completed run.</p>
<p>Both objective failures were classified server-side as:</p>
<ul>{failure_items}</ul>
<p class="note"><strong>Uncertainty:</strong> the two-sided 95% Wilson interval for the underlying failure probability is {pct(wilson[0])}–{pct(wilson[1])}. This interval is intentionally broad: twenty trials characterize this frozen setup; they do not establish a universal reliability rate.</p>
</section>

<section>
<h2>Outcome evidence and retention</h2>
<div class="trials" aria-label="Twenty trial records">{''.join(trial_cells)}</div>
<p>The canonical aggregate is immutable: 18 recoveries and 2 failures. The original M1C runner did not durably retain the complete per-trial evidence contract, so M2 does not guess which historical ordinals produced those aggregate outcomes. Gray cells mean that the per-trial outcome was not retained. Trial 20 contains the concrete evidence preserved from the final run output.</p>
</section>

<section>
<h2>Why the oracle matters</h2>
<p>PASS/FAIL is determined by <code>{esc(oracle['source'])}</code>. The agent's own final message is explicitly not the oracle. A successful run required the target product, quantity one, Standard shipping, final review stage, and no submitted payment.</p>
</section>

<section>
<h2>How Agent Crash Lab got here</h2>
<p><strong>M0:</strong> proved that a deterministic UI mutation could break a brittle scripted policy. <strong>M1A:</strong> moved to an autonomous browser-use agent; the baseline, singles, and pairs all passed, so the result was inconclusive. <strong>M1B:</strong> introduced frozen deterministic state-machine perturbations and found that <code>review_rollback</code> produced divergent outcomes across confirmations, so it was not a deterministic breaker. <strong>M1C:</strong> kept that exact condition frozen and characterized recovery across twenty valid autonomous trials, producing the 18/2 result shown here.</p>
</section>

<section>
<h2>Replay evidence</h2>
<p>{esc(replay['note'])} Replay availability was confirmed during the live run: {esc(display(replay['availability_confirmed_during_live_run']))}. Signed capability URLs are not committed or rendered by this report.</p>
</section>

<section>
<h2>Per-trial sanitized evidence</h2>
<div class="table-wrap"><table>
<thead><tr><th>Trial</th><th>Perturbation</th><th>Fingerprint</th><th>Outcome</th><th>Failure class</th><th>Final state</th><th>Authoritative events</th><th>Replay</th><th>Agent/browser status</th><th>Retention</th></tr></thead>
<tbody>{''.join(trial_rows)}</tbody>
</table></div>
</section>

<section>
<h2>Frozen configuration</h2>
<p>Milestone: <code>{esc(experiment['milestone'])}</code> · status: <code>{esc(experiment['status'])}</code> · model: <code>{esc(experiment['model'])}</code> · perturbation: <code>{esc(experiment['condition'])}</code> · frozen implementation commit: <code>{esc(experiment['frozen_implementation_commit'])}</code>.</p>
<p class="note">{esc(experiment['interpretation_scope'])}</p>
</section>

<footer>Generated deterministically from the sanitized M2 evidence artifact. No Solari, OpenAI, browser-use, network, or live-service access is required.</footer>
</body>
</html>
"""
    assert_secret_free_text(document)
    return document


def generate_report(evidence_path: Path, output_path: Path) -> Path:
    data = validate_evidence_file(evidence_path)
    rendered = render_report(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8", newline="\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the offline M1C evidence report.")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    path = generate_report(args.evidence, args.output)
    print(f"M2 report generated: {path}")


if __name__ == "__main__":
    main()
