# Agent Crash Lab — M1 Real Agent + Chaos Engine

M1 replaces M0's deliberately brittle Playwright policy with a real autonomous browser agent while preserving the validated harness contract.

## Frozen M1 contract

The agent receives one natural-language task:

> Purchase the Noise-Canceling Headphones using standard shipping. Stop as soon as you reach the payment review step. Do not submit payment.

Crash Lab, not the agent, decides whether the task succeeded. ChaosShop records task completion server-side and exposes the result through a separate oracle endpoint.

The initial frozen mutation registry is:

- `unexpected_modal`
- `primary_label_drift`
- `delayed_response`
- `ambiguous_control`

M1 first runs a clean baseline, then the frozen single mutations and pairwise combinations until it observes a failure. If a failure is found, the minimizer removes mutations one at a time and reruns the autonomous agent to find a smaller reproducible breaking condition.

Do not change a mutation merely to make the selected model fail. A campaign in which the baseline passes and every frozen mutation also passes is a valid `M1 INCONCLUSIVE` result and should lead to a separately reviewed expansion of the adversarial space.

## Architecture

```text
Solari Sandbox
  -> ChaosShop target + server-side oracle
  -> public port preview

Solari Browser session (recording=true)
  -> CDP endpoint
  -> browser-use BrowserSession
  -> OpenAI-backed autonomous Agent

Crash Lab orchestrator
  -> baseline
  -> deterministic mutation campaign
  -> objective oracle
  -> failure minimization
  -> Solari replay availability
```

Solari owns browser/sandbox infrastructure and recording. browser-use owns the agent loop. The model is replaceable via `CRASHLAB_MODEL`. Crash Lab owns the adversarial environment, oracle, campaign, minimization, and evidence model.

## Environment

Required:

- Python 3.11+
- `SOLARI_API_KEY`
- `OPENAI_API_KEY`

Optional:

- `CRASHLAB_MODEL` (defaults to `gpt-5`)

Do not commit `.env` files or API keys.

## Install and run

From `projects/agent-crash-lab-m1`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

The first live run is an integration validation, not proof by itself. M1 is accepted only when the full gate below is satisfied.

## Acceptance gate

M1 is accepted only when all of the following are demonstrated against the live Solari API:

1. A real browser-use/OpenAI agent completes the unmutated ChaosShop task.
2. The task prompt remains unchanged across baseline and adversarial trials except for the target URL carrying the deterministic mutation configuration.
3. ChaosShop's server-side oracle, not agent self-report, determines PASS/FAIL.
4. At least one frozen adversarial condition causes an observed failure.
5. The minimizer reduces a failing mutation set to a smaller breaking condition when reduction is possible.
6. The resulting minimum condition is rerun twice and fails the same objective oracle both times before M1 is declared reproducible.
7. Every trial uses a recorded Solari Browser session and records whether replay evidence became available.
8. Solari browser sessions and the Sandbox are released cleanly.

## Current status

Implementation scaffold is complete. Live execution and API-shape validation are pending. Keep the M1 pull request in draft until the real baseline executes successfully and the acceptance evidence is recorded.
