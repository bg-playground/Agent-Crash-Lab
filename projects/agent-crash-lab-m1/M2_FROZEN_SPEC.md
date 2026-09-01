# M2 Frozen Spec — Evidence Reporting and Presentation

Status: **FROZEN BEFORE M2 IMPLEMENTATION**  
Date: 2026-09-01

## Purpose

M2 does not create a new reliability experiment and does not tune M1C. Its job is to turn the already-completed M1C characterization into a durable, security-sanitized evidence package that a reviewer can inspect without reading raw browser-use logs.

The canonical M1C result is fixed:

- model: `gpt-5`
- condition: `review_rollback`
- valid trials: 20
- infrastructure-invalid attempts: 0
- recoveries: 18
- failures: 2
- recovery rate: 90.0%
- failure rate: 10.0%
- failure classes: `incomplete_at_shipping` × 2
- two-sided 95% Wilson interval for failure probability: `[0.028, 0.301]`
- frozen M1C implementation commit: `d45a0b66bdf5e6441408513987a655e19978c26b`

M2 must preserve that result exactly. No rerun, reinterpretation, filtering, trial removal, perturbation change, prompt change, model change, or statistical-method change is part of this milestone.

## Product thesis for M2

Agent Crash Lab should make one result immediately legible:

> The same autonomous agent, given the same task and the same deterministic rollback perturbation, recovered in 18 of 20 valid runs and failed in 2 of 20.

The evidence experience should show both aggregate reliability and the concrete behavioral path that produced each outcome.

## Scope

M2 includes only evidence packaging and presentation for the completed M1C result.

### 1. Sanitized machine-readable evidence artifact

Produce a committed or reproducibly generated structured artifact that contains the canonical M1C characterization and a per-trial evidence schema.

The schema must support, for every valid trial:

- ordinal trial number;
- perturbation name;
- non-sensitive run fingerprint;
- objective PASS/FAIL;
- server-side failure class;
- final authoritative state summary;
- ordered authoritative event history;
- replay availability boolean;
- agent/browser error status.

The artifact must never contain:

- Solari preview URLs;
- `pt_token` values;
- CDP or WebSocket endpoints;
- raw Solari browser/session IDs;
- raw sandbox IDs;
- signed replay URLs;
- API keys or other credentials.

If historical live-run data required for a per-trial field was not captured durably during M1C, M2 must not invent it. Such fields must be represented explicitly as unavailable/not retained, with the aggregate M1C result kept unchanged.

### 2. Deterministic report generator

Add a report generator that consumes only sanitized evidence data and produces a standalone reviewer-facing report.

The generator must not contact Solari, OpenAI, browser-use, or any live external service. It must be deterministic for a fixed input artifact.

Preferred output:

- standalone HTML report suitable for opening locally or publishing as a static artifact.

A Markdown summary may also be generated, but HTML is the primary presentation target.

### 3. Reviewer-facing report content

The report must contain:

- Agent Crash Lab title and one-sentence thesis;
- frozen experiment configuration;
- 18/20 recovery and 2/20 failure headline;
- 90.0% recovery rate and 10.0% failure rate;
- 95% Wilson interval `[2.8%, 30.1%]` with a plain-language uncertainty note;
- failure-class breakdown showing both failures as `incomplete_at_shipping`;
- a 20-trial outcome strip/table or equivalent visual summary;
- per-trial evidence table using only sanitized fields actually retained;
- clear explanation that server-authoritative state, not agent self-report, determines PASS/FAIL;
- concise history of M0 → M1A → M1B → M1C so reviewers understand how the characterization was reached;
- explicit guardrail that this is a finite-sample result for one frozen agent/task/environment configuration, not a universal model reliability claim.

### 4. Replay presentation contract

M2 may show replay status and may support reviewer-provided replay references, but it must not commit or render signed replay URLs or other credential-bearing capability links.

If durable public-safe replay links do not exist, the report must say that replay evidence was confirmed available during the run but signed capability URLs are intentionally excluded from committed evidence.

### 5. Repository documentation

Update the project README/status documentation so a reviewer can discover:

- what M1C established;
- where the sanitized evidence artifact lives;
- how to regenerate the report offline;
- where to open the generated report;
- what remains intentionally out of scope.

## Explicitly out of scope

M2 must not:

- rerun M1C to improve or complete evidence;
- change the 20-trial sample;
- tune `review_rollback`;
- change task prompt, model, model settings, max steps, or oracle rules;
- add new perturbations;
- claim that `review_rollback` is a deterministic breaker;
- build a hosted SaaS dashboard;
- add authentication, accounts, persistence services, or a backend database;
- introduce a new frontend framework solely for this report;
- require live Solari access to view the evidence;
- expose credential-bearing replay or preview links;
- present unavailable per-trial historical fields as if they were observed.

Parallel execution is also out of scope for the first M2 implementation PR. If later desired, it requires a separate bounded review because concurrency changes infrastructure behavior and is not necessary to present the completed M1C result.

## Data-integrity rules

1. The aggregate numbers above are canonical and immutable in M2.
2. Report generation must derive displayed percentages and counts from the sanitized evidence artifact rather than duplicate hand-maintained values where practical.
3. The Wilson interval implementation must either reuse the already-tested M1C computation or validate the canonical interval in offline tests; M2 must not introduce a different confidence-interval method.
4. Missing historical per-trial data must remain missing rather than reconstructed from agent prose or guessed from aggregate counts.
5. Agent final messages may be shown only as illustrative context and must never override the server-side oracle.
6. Security sanitization is a correctness requirement, not cosmetic cleanup.

## Acceptance criteria

M2 is complete only when all of the following are true:

1. A sanitized structured evidence artifact exists and contains no capability secrets.
2. The artifact represents the canonical 20-valid-trial M1C characterization without changing counts or outcomes.
3. A deterministic offline command generates the primary HTML report from the sanitized artifact.
4. The generated report clearly shows 18 recoveries, 2 failures, 90.0% recovery, 10.0% failure, and the 95% Wilson interval `[2.8%, 30.1%]`.
5. Both failures are represented as `incomplete_at_shipping`.
6. The report explains the server-authoritative oracle and the finite-sample interpretation guardrail.
7. The report includes a 20-trial visual/table representation and per-trial evidence using only fields actually retained.
8. Any unavailable historical per-trial fields are labeled unavailable/not retained rather than fabricated.
9. Replay evidence is described without committing signed capability URLs or credentials.
10. Automated offline tests validate deterministic rendering, canonical aggregate values, and secret-sanitization invariants.
11. Existing M1B/M1C offline tests remain green.
12. README/status documentation points reviewers to the evidence artifact and report-generation command.
13. No live Solari/OpenAI call is required to generate or inspect the report.
14. No experiment semantics are modified.

## Recommended implementation sequence

M2 should be delivered in bounded PRs:

1. **M2 PR 1 — Evidence contract and sanitized canonical artifact**  
   Define the schema, encode the frozen M1C aggregate result, represent only genuinely retained per-trial evidence, and add sanitization/contract tests.

2. **M2 PR 2 — Deterministic HTML evidence report**  
   Generate a standalone static report from the artifact with aggregate summary, failure-class breakdown, trial matrix/table, uncertainty note, and security-safe replay status.

3. **M2 PR 3 — Reviewer documentation and submission polish**  
   Update README/status docs, add the one-command offline generation path, and perform a bounded reviewer-facing presentation audit.

Do not begin parallel-trial orchestration or a hosted dashboard inside these PRs.

## Completion gate

The milestone is complete when a reviewer can clone the repository, run one offline report-generation command, open a standalone evidence report, and understand what Agent Crash Lab discovered—without needing credentials, live infrastructure, raw logs, or trust in the agent's own success claims.
