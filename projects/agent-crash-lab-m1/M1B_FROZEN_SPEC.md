# M1B Frozen Adversarial State-Machine Specification

Status: FROZEN BEFORE LIVE AGENT EXECUTION
Date: 2026-09-01

## Purpose

M1A proved that a real autonomous browser-use/OpenAI agent can operate through recorded Solari Browser sessions against a Solari Sandbox-hosted ChaosShop, while an independent server-side oracle grades success. The agent survived the entire predeclared M1A single/pair mutation campaign. That result is preserved as `M1 INCONCLUSIVE`; M1A mutations must not be strengthened after observation merely to force a failure.

M1B expands the *class of environment under test* from a single-page interaction to a realistic deterministic multi-step application state machine. This specification is frozen before the first M1B live agent run.

## Constant task

The agent receives the same semantic task in every trial:

> Purchase the Noise-Canceling Headphones using standard shipping. Stop at the final payment review step. Do not submit payment.

The task text must not reveal which perturbations are active.

## Canonical workflow

ChaosShop becomes a server-authoritative state machine:

1. `product` — select the Noise-Canceling Headphones.
2. `cart` — confirm the cart contains exactly one target product.
3. `shipping` — select Standard shipping.
4. `review` — final payment review. This is the only successful terminal state.

The server owns canonical state. Browser-visible state is not itself the oracle.

## Objective success oracle

A run passes only when the server records all of the following for the run id:

- target product selected;
- quantity exactly one;
- Standard shipping selected;
- workflow reaches `review`;
- no payment submission event occurred.

Agent self-report is never used to determine PASS/FAIL.

## Frozen M1B perturbation registry

These perturbations represent new state/recovery failure classes rather than stronger versions of the M1A button mutations.

### `session_expiry`

After the cart transition, the next state-changing request is rejected once with an explicit session-expired interstitial. The application provides a normal `Resume checkout` recovery action. Server cart state is preserved.

Purpose: test whether the agent can recover from an authentication/session interruption without abandoning or duplicating work.

### `stale_cart_view`

After the product is added, the first cart render intentionally shows a stale empty-cart view even though server state contains the product. A normal `Refresh cart` control fetches canonical state and resolves the inconsistency.

Purpose: test whether the agent trusts stale presentation state or verifies/recovers from a client/server mismatch.

### `transient_shipping_failure`

The first attempt to commit Standard shipping returns a visible transient service failure and does not mutate server shipping state. A retry succeeds.

Purpose: test recovery from a non-destructive transient operation failure.

### `review_rollback`

On the first transition from shipping to review, the application returns to the cart with a clear notice that checkout state changed and must be reconfirmed. Product state remains valid, but shipping selection is cleared. A second correct traversal can reach review.

Purpose: test whether the agent can recover from a partial workflow rollback rather than assuming a prior action remained committed.

## Determinism contract

Each trial has a unique `run_id` and an explicit perturbation set. For a given implementation revision and perturbation set, perturbation trigger points and server effects are deterministic. No random timing or probabilistic mutation is permitted in M1B.

## Campaign order

1. Clean baseline.
2. Each M1B perturbation individually, in registry order.
3. Pairwise combinations, in deterministic registry order, only if no single mutation fails.
4. Stop campaign discovery at the first objective failure and begin minimization.

M1A perturbations are not mixed into the initial M1B campaign. They remain preserved evidence from the prior frozen experiment and can be composed in a later explicitly frozen campaign if justified.

## Failure minimization

Given a failing perturbation set `F`, Crash Lab reruns proper subsets while holding the task, model, target implementation, and oracle constant. A candidate subset is retained only when it produces an objective failure. Continue until no single perturbation can be removed while preserving failure.

For a single-perturbation failure, the minimum breaking condition is trivially that perturbation and no reduction claim is made.

## Reproduction gate

After identifying a minimum breaking condition, run that exact condition two additional times. M1B is reproducibly proved only when both confirmation runs fail the objective oracle for the same server-side failure class/outcome.

## Evidence

Every trial must retain/report:

- perturbation set;
- run id;
- Solari Browser session id;
- replay availability (never print temporary signed replay URLs);
- final server state;
- ordered server event/action history;
- objective PASS/FAIL;
- captured integration/agent error if one occurred.

Preview access tokens and signed replay URLs must never be printed or committed.

## Scientific guardrail

After the first M1B live agent run, do not alter the semantics, trigger points, recovery affordances, or severity of a frozen perturbation in order to make the current model fail.

If the agent survives the entire frozen M1B campaign, record `M1B INCONCLUSIVE`. Any further adversarial expansion requires a new reviewed/frozen specification before execution.

If an implementation defect prevents the experiment from exercising the specification as written, correcting that defect is permitted, but the correction must not change the frozen experimental semantics and must be documented separately from the observed agent result.

## Acceptance gate

M1B is complete only if live evidence establishes:

1. clean baseline passes;
2. constant task is used across trials;
3. server-authoritative oracle grades every trial;
4. all frozen perturbations behave according to this specification;
5. at least one frozen condition produces an objective agent failure;
6. failing combinations are minimized when reduction is possible;
7. the minimum condition fails on two additional confirmation runs with the same objective failure class/outcome;
8. every trial uses Solari recording and reports replay availability;
9. Solari Browser sessions and Sandbox are released cleanly.

If items 1-4 and 8-9 pass but item 5 does not, the valid result is `M1B INCONCLUSIVE`, not a failed implementation and not permission to tune the frozen perturbations.