# Agent Crash Lab — reviewer brief

## One sentence

Agent Crash Lab uses Solari-hosted deterministic adversarial environments, recorded Solari Browsers, and server-authoritative oracles to measure whether autonomous computer-use agents recover reliably when reality stops behaving like the demo.

## Result worth inspecting

**Same autonomous agent. Same task. Same deterministic `review_rollback` perturbation. Twenty valid runs: 18 recoveries, 2 objective failures.**

Both failures were `incomplete_at_shipping`. The observed failure rate was 10.0%, with a two-sided 95% Wilson interval of 2.8%–30.1% for this frozen setup.

This is intentionally a characterization, not a claim that the model fails 10% of the time in general.

## Fastest review path

1. Read `README.md` for the architecture and M0 → M1C experiment story.
2. Inspect `M1C_FROZEN_SPEC.md` to see the protocol frozen before the 20-valid-trial execution.
3. Inspect `evidence/m1c_characterization.json` for the sanitized canonical result and explicit retention gaps.
4. Run `python m2_report.py`, then open `evidence/m1c_report.html` for the standalone reviewer-facing evidence report.
5. Run the offline test gate:

```powershell
python -m unittest -v test_m1b_state_machine.py test_m1b_campaign.py test_m1c_reliability.py test_m2_evidence.py test_m2_report.py
```

Expected current result: 41 tests, all passing.

## What Solari contributes

Crash Lab uses Solari for the infrastructure that makes this experiment practical and inspectable:

- a Sandbox hosts the deterministic ChaosShop target and authoritative state machine;
- a Solari preview exposes the target to the remote browser;
- a recorded Solari Browser provides the real browser session used by browser-use;
- replay availability is checked for live trials;
- browser and sandbox resources are explicitly released after use.

Crash Lab deliberately does not commit credential-bearing preview, CDP/WS, session, sandbox, or signed replay capabilities.

## What Crash Lab contributes

The project-specific layer is the reliability methodology around that infrastructure:

- deterministic adversarial environment mutations and state-machine perturbations;
- experiment freeze rules that prevent tuning after seeing outcomes;
- an objective server-side oracle independent of agent self-report;
- infrastructure-invalid versus agent-failure classification;
- minimum-breaking-condition search in the earlier campaign;
- repeated valid-trial reliability characterization when deterministic reproduction did not hold;
- sanitized evidence contracts and deterministic offline reporting.

## Why the inconclusive stages matter

M1A did not produce a failure, and M1B did not prove a deterministic breaker. Those are not hidden or rewritten as successes. M1A was recorded as inconclusive. M1B's two confirmation runs diverged. That divergence motivated the frozen M1C question: how often does the same agent recover under the exact same deterministic rollback condition?

The resulting 18/20 versus 2/20 split is more useful than forcing a brittle demo failure because it exposes a reliability property that a single run cannot reveal.

## Evidence limitation

The original M1C live runner did not durably persist the full per-trial evidence contract for trials 1–19. The aggregate result and both failure classes are canonical, but M2 does not invent which historical ordinals failed. The sanitized artifact and HTML report mark missing per-trial fields unavailable. Trial 20 contains the concrete retained evidence available from the final run output.

That limitation is part of the evidence package because trustworthy agent evaluation should make missing evidence visible rather than silently reconstruct it.

## Scope guardrail

The completed M1C result is frozen. Submission polish must not change the model, prompt, task, perturbation, step budget, oracle, sample size, Wilson method, or canonical 18/2 result. Future experiments can extend Crash Lab, but they should be separately specified rather than retrofitted onto this characterization.
