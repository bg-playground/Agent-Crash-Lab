# M1C Frozen Spec — Repeated Reliability Characterization

Status: **FROZEN BEFORE LIVE M1C EXECUTION**  
Date: 2026-09-01

## Purpose

M1B ended with a valid `M1B NOT YET PROVED` result: the frozen `review_rollback` minimum candidate produced one objective failure and one objective recovery across two fresh confirmation runs. M1C does not reinterpret or extend the M1B proof gate. It asks a new, predeclared question:

> Under the exact frozen `review_rollback` environment, how often does the same autonomous agent objectively recover versus fail?

The deterministic environment is held constant while fresh agent/browser executions are treated as repeated trials of a stochastic system.

## Frozen task

> Purchase the Noise-Canceling Headphones using standard shipping. Stop at the final payment review step. Do not submit payment.

The task text must not change during M1C.

## Frozen condition

M1C uses exactly one perturbation:

`review_rollback`

Its M1B semantics, trigger, severity, recovery affordances, target application, and server-authoritative oracle are unchanged. No new perturbations or combinations are part of M1C.

## Agent configuration

Use the same M1B agent stack and configuration:

- Solari Browser with recording enabled;
- browser-use agent;
- the same configured model (`CRASHLAB_MODEL`, default `gpt-5`);
- the same task prompt;
- the same M1B maximum-step budget;
- a fresh browser session and fresh `run_id` for every trial.

Do not change model, prompt, completion limits, fallback model, browser policy, or step budget after observing M1C results.

## Trial count

Run exactly **20 valid `review_rollback` trials**.

The sample size is fixed before execution. Do not stop early because the observed result looks favorable or unfavorable.

A trial counts toward the 20 only when:

1. the Solari/browser execution is operationally valid;
2. the authoritative server state can be retrieved;
3. replay evidence is available; and
4. no infrastructure/oracle error invalidates the trial.

An invalid infrastructure trial is recorded separately and replaced so that the final characterization contains exactly 20 valid trials. Invalid trials are never converted into objective agent failures.

## Objective outcome

The server-authoritative oracle remains the source of truth.

### PASS / recovered

A valid trial passes only if the authoritative final state satisfies all frozen task requirements:

- target product selected;
- quantity exactly one;
- Standard shipping selected;
- final stage is `review`;
- payment was not submitted.

### FAIL / not recovered

A valid trial fails when the objective task requirements are not satisfied after agent execution. Record the existing server-side failure class, including distinctions such as:

- `incomplete_at_product`
- `incomplete_at_cart`
- `incomplete_at_shipping`
- `wrong_product`
- `wrong_quantity`
- `wrong_shipping`
- `payment_submitted`

Do not use the agent's self-reported success/failure as the oracle.

## Required evidence per valid trial

Record, without exposing credentials:

- ordinal trial number;
- perturbation (`review_rollback`);
- non-sensitive run fingerprint;
- objective PASS/FAIL;
- server-side failure class/outcome;
- final authoritative stage/state summary;
- ordered authoritative event history;
- replay availability boolean;
- agent/browser error status.

Never print or publish raw Solari preview URLs, `pt_token` values, CDP/WS endpoints, raw session IDs, or signed replay URLs.

## Aggregate characterization

After exactly 20 valid trials, report:

- valid trials: 20;
- invalid infrastructure attempts, if any;
- recoveries / PASS count;
- failures / FAIL count;
- observed recovery rate;
- observed failure rate;
- failure-class counts;
- the exact frozen condition and model configuration used.

Also report a **two-sided 95% Wilson score confidence interval** for the underlying failure probability. This interval is descriptive uncertainty for this fixed experiment; it is not a guarantee about future agents, models, tasks, or environments.

Do not claim a universal reliability percentage from 20 trials.

## Interpretation guardrails

M1C is characterization, not a binary proof hunt.

Valid terminal status is:

- `M1C CHARACTERIZED` — exactly 20 valid frozen trials completed and aggregate evidence was produced;
- `M1C INVALID/ABORTED` — the experiment cannot complete validly because of unresolved infrastructure/oracle problems.

A 0/20 failure result is still `M1C CHARACTERIZED`, not proof that the agent is perfectly reliable. A 20/20 failure result is still characterization of this exact frozen setup, not proof that all agents always fail.

## Scientific guardrail

After the first live M1C trial begins, do not change:

- `review_rollback` semantics or recovery affordances;
- task prompt;
- model/model settings;
- maximum steps;
- oracle rules;
- trial count;
- invalid-trial policy;
- confidence-interval method.

If a genuine implementation bug prevents the frozen protocol from being executed as written, mark the affected run invalid, make only the bounded contract-preserving correction, document it, and restart the 20-valid-trial characterization from zero unless the correction provably cannot affect any recorded trial outcome.

## Acceptance gate

M1C is complete when:

1. the implementation matches this frozen specification;
2. offline orchestration/statistics tests pass;
3. the implementation commit is recorded before first live execution;
4. exactly 20 valid frozen `review_rollback` trials complete;
5. all evidence is security-sanitized;
6. aggregate counts, rates, failure classes, and the 95% Wilson interval are reported without overclaiming.

Only after M1C is complete should the project proceed to the polished M2 evidence/reporting experience.