# Agent Crash Lab — adversarial reliability testing for computer-use agents

> Your AI agent passed the demo. Crash Lab finds out whether it survives reality.

Agent Crash Lab is a reproducible chaos-engineering harness for autonomous browser agents. It uses Solari Sandboxes to host deterministic adversarial web environments and recorded Solari Browser sessions to run a real browser-use agent against them. Crash Lab then judges the result with server-authoritative state rather than trusting the agent's own final message.

The most important result so far is deliberately narrower than a benchmark claim:

> **Same autonomous agent. Same task. Same deterministic rollback perturbation. Twenty valid runs: 18 recoveries, 2 objective failures.**

Both failures ended `incomplete_at_shipping`. The observed failure rate was 10.0%; the two-sided 95% Wilson interval for the underlying failure probability in this frozen setup is 2.8%–30.1%. This is a finite-sample characterization of one frozen agent/task/environment configuration, not a universal model reliability guarantee.

## Why this is interesting

A single successful demo does not establish agent reliability. Even when the environment perturbation itself is deterministic, an autonomous agent can recover on one run and fail on another. Crash Lab makes that behavior measurable by freezing the task and environment, repeating valid trials, and preserving objective evidence.

The project is intentionally built around experiment integrity:

- perturbations are frozen before observing the result;
- the task prompt and agent configuration stay fixed within an experiment;
- server-side state is the PASS/FAIL oracle;
- infrastructure-invalid attempts are not counted as agent failures;
- missing historical evidence is labeled unavailable rather than reconstructed or guessed;
- credential-bearing Solari preview, CDP/WS, session, and replay capabilities are never committed as evidence.

## Architecture

```text
Solari Sandbox
  -> deterministic ChaosShop target
  -> server-authoritative task state / event oracle
  -> Solari preview capability

Solari Browser (recording enabled)
  -> CDP connection
  -> browser-use autonomous agent
  -> provider-backed LLM

Agent Crash Lab
  -> frozen perturbation campaign
  -> objective PASS / FAIL classification
  -> failure minimization / repeated characterization
  -> sanitized evidence artifact
  -> deterministic offline HTML evidence report
```

Solari owns the remote browser/sandbox infrastructure and session recording. browser-use owns the autonomous agent loop. Crash Lab owns the adversarial environment, experiment protocol, oracle, reliability characterization, sanitization, and evidence presentation.

## Evidence report

M2 turns the completed M1C experiment into an inspectable offline evidence package.

Canonical sanitized evidence:

```text
evidence/m1c_characterization.json
```

Deterministic report generator:

```text
m2_report.py
```

Generate and open the standalone report from `projects/agent-crash-lab-m1`:

```powershell
python m2_report.py
Start-Process .\evidence\m1c_report.html
```

The generated HTML has no JavaScript, external assets, network dependency, Solari call, OpenAI call, or browser-use call. It is rendered from the sanitized evidence artifact and passed through the evidence secret/capability sanitizer before being written.

The report presents the canonical 18/20 recovery result, uncertainty interval, failure-class breakdown, server-authoritative oracle, experiment history, replay policy, and the per-trial evidence that was actually retained. The original M1C runner did not durably retain the complete evidence contract for trials 1–19, so M2 explicitly marks those individual fields unavailable instead of guessing which historical ordinals were the two failures. Trial 20 contains the concrete retained PASS evidence.

## Experiment history

### M0 — prove the harness

M0 used a deliberately brittle Playwright policy and showed that one deterministic mutation could turn a passing task into a reproducible failure. This validated the Solari-hosted target, objective state, browser recording, and basic adversarial harness.

### M1A — move to a real autonomous agent

The scripted policy was replaced with browser-use plus an OpenAI-backed model. The clean baseline, all frozen single mutations, and all six frozen mutation pairs passed the objective oracle. The correct conclusion was **M1 INCONCLUSIVE**, not to tune the mutations after seeing the result.

### M1B — state-machine reliability perturbations

ChaosShop became a multi-step authoritative state machine with four frozen reliability perturbations: session expiry, stale cart view, transient shipping failure, and review rollback. Failure minimization identified `review_rollback` as the minimum candidate, but two required confirmation reruns diverged: one failed at shipping and one recovered to review. Therefore M1B was **NOT YET PROVED** as a deterministic breaker.

That divergence became the more interesting question.

### M1C — characterize stochastic recovery

M1C froze the exact `review_rollback` environment and the same autonomous agent/task configuration, then required exactly 20 valid trials with no early stopping. The completed characterization produced:

| Measure | Result |
| --- | ---: |
| Valid trials | 20 |
| Infrastructure-invalid attempts in canonical completed run | 0 |
| Recoveries | 18 |
| Objective failures | 2 |
| Recovery rate | 90.0% |
| Failure rate | 10.0% |
| Failure class | `incomplete_at_shipping` × 2 |
| Failure probability, 95% Wilson interval | 2.8%–30.1% |

The scientific result is not that `review_rollback` always breaks the agent. It is that the same deterministic environment condition produced materially different autonomous outcomes, and Crash Lab can characterize that reliability rather than hiding it behind a single successful demo.

## Run the validation gates

Create/activate a Python 3.11+ environment and install `requirements.txt` for the live agent dependencies. The M2 evidence/report path itself is offline once the canonical artifact exists.

From `projects/agent-crash-lab-m1`:

```powershell
python -m unittest -v test_m1b_state_machine.py test_m1b_campaign.py test_m1c_reliability.py test_m2_evidence.py test_m2_report.py test_reliability_stats.py test_model_version_log.py test_calibration.py test_typed_answers.py test_run_mode.py test_m1b_live_model_log.py
python m2_report.py
```

The current combined offline gate is 92 tests: 41 experiment/evidence tests plus 51 measurement-harness tests. None of them call Solari, a browser, or a model provider; the harness tests use fakes and `httpx.MockTransport`.

Live experiments additionally require `SOLARI_API_KEY` and `OPENAI_API_KEY`. `CRASHLAB_MODEL` is optional and defaults to the model frozen by the relevant experiment. Never commit `.env` files, API keys, preview URLs, CDP/WS endpoints, raw session/sandbox identifiers, or signed replay capabilities.

## Repository map

- `main.py` — original M1A autonomous-agent campaign.
- `m1b_state_machine.py` — deterministic ChaosShop state machine and perturbations.
- `m1b_live.py` — live Solari/browser-use integration.
- `M1B_FROZEN_SPEC.md` — frozen M1B protocol.
- `m1c_reliability.py` — repeated M1C reliability characterization runner.
- `M1C_FROZEN_SPEC.md` — frozen 20-valid-trial M1C protocol.
- `M2_FROZEN_SPEC.md` — frozen evidence/reporting milestone contract.
- `m2_evidence.py` — sanitized evidence contract and validator.
- `evidence/m1c_characterization.json` — canonical sanitized M1C evidence artifact.
- `m2_report.py` — deterministic standalone HTML evidence renderer.
- `test_m2_evidence.py`, `test_m2_report.py` — evidence integrity, sanitization, and report tests.
- `reliability_stats.py` — shared `wilson_interval()` (moved unchanged from `m1c_reliability.py`, which re-exports it).
- `run_log.py` — append-only JSONL run-log helper.
- `model_version_log.py` — per-call returned-model-version log with `restart` / `mark_invalid` policies and an httpx hook for OpenAI-compatible clients.
- `calibration.py` — confidence-binned calibration table with Wilson intervals and a minimum-count "not measured" rule.
- `typed_answers.py` — yes/no, choice-from-list, and fixed-scale score parser; malformed answers become explicit MISSING results.
- `run_mode.py` — shadow-then-score switch, frozen threshold checks, and a decision/rejection log.

## Measurement harness modules

These modules are generic: they do not depend on Solari or browser-use and can back a client harness. They do not change the frozen M1B/M1C protocols or the canonical M1C evidence.

Per-call model version (the provider-returned `model`, not the requested family):

```python
from model_version_log import ModelVersionLog, ModelVersionChanged

log = ModelVersionLog("runs/model_calls.jsonl", run_id, policy="restart")  # or "mark_invalid"
response = client.chat.completions.create(model="gpt-5", messages=messages)
log.record("gpt-5", response.model)          # raises ModelVersionChanged/ModelVersionMissing under restart
summary = log.write_summary()                 # run_valid, versions_seen, changed/missing call ids
```

For SDKs that accept an `httpx.AsyncClient`, `ModelVersionHttpHook.async_client(log)` records every successful call without raising into the SDK; poll `log.restart_required` or call `log.raise_if_restart_required()`. `m1b_live.run_trial(..., model_version_log_path=...)` uses this path (opt-in; the default trial path is unchanged).

Calibration table:

```python
from calibration import CalibrationTable, JudgedAnswer

table = CalibrationTable.build([JudgedAnswer(0.8, True), ...], min_count=10, missing_count=n_missing)
print(CalibrationTable.to_markdown(table)); CalibrationTable.to_json(table)
```

Typed answers and shadow-then-score:

```python
from typed_answers import ChoiceQuestion, TypedAnswerParser
from run_mode import DecisionLedger, RunMode, ThresholdCheck

question = ChoiceQuestion("department", ("billing", "technical"))
answer = TypedAnswerParser.parse(question, model_text)       # ParsedAnswer or MissingAnswer(reason)
checks = [ThresholdCheck("department_confidence_floor", "confidence", ">=", 0.6)]

shadow = DecisionLedger("runs/decisions.jsonl", "shadow-1", RunMode.SHADOW, checks)
shadow.decide("route", "department_confidence_floor", answer, action=route)   # logged, never acted
shadow.finish()
score = DecisionLedger("runs/decisions.jsonl", "score-1", RunMode.SCORE, checks, shadow_run_id="shadow-1")
```

## Current status

**M1C CHARACTERIZED. M2 evidence artifact and deterministic HTML report complete.**

The project has moved from proving that an adversarial harness can create failures to measuring a more realistic reliability problem: an autonomous agent can respond differently to the same deterministic disruption. The next work should focus on reviewer/submission presentation and future experiment design without reopening or tuning the completed M1C result.
