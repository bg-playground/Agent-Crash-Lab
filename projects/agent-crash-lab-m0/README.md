# Agent Crash Lab — M0 Deterministic Failure Proof

M0 proves the technical heart of Agent Crash Lab with the smallest useful vertical slice:

1. Launch a controlled target application inside a Solari sandbox.
2. Expose it through Solari's public port preview.
3. Run a baseline browser workflow with session recording enabled.
4. Re-run the same workflow against a deterministic mutation seed.
5. Repeat the same seed and require the failure to reproduce.
6. Print the Solari session/replay evidence for every trial.

This milestone intentionally uses a brittle computer-use policy rather than an LLM agent. The acceptance criterion is infrastructure-level: prove that Crash Lab can turn a passing workflow into a deterministic, reproducible failure with recorded evidence. A later milestone replaces the policy with an actual autonomous agent without changing the core test-harness contract.

## Mutation

Seed `48291` injects an unexpected modal whose action has the same accessible label (`Continue`) as the underlying task action. The baseline contains one matching action; the mutated environment contains two. The intentionally brittle policy therefore fails under the mutation.

## Run

```powershell
cd projects/agent-crash-lab-m0
npm install
npm start
```

`SOLARI_API_KEY` must already exist in the environment.

A successful M0 run ends with:

```text
M0 PROVED
Baseline passes; seed 48291 fails twice with the same deterministic mutation.
```

The output also includes the Solari browser session id and replay URL when the asynchronous replay is ready.

## M0 acceptance gate

M0 is accepted only when all of the following are true against the real Solari API:

- baseline trial passes;
- seeded trial fails;
- the same seed fails again;
- both failures arise from the same deterministic mutation;
- recorded Solari session evidence is available;
- sandbox and browser resources are released after execution.
