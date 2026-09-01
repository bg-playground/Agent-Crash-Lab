from __future__ import annotations

import asyncio
import itertools
import os
from collections.abc import Iterable

from solari_browser import Solari
from solari_sandbox import SandboxClient

from m1b_live import (
    BASE_URL,
    CHAOSSHOP_SERVER,
    MODEL,
    PORT,
    Trial,
    run_trial,
)
from m1b_state_machine import PERTURBATIONS

CONFIRMATION_RUNS = 2


def print_trial(label: str, mutations: tuple[str, ...], trial: Trial) -> None:
    status = "PASS" if trial.passed else "FAIL"
    mutation_label = ",".join(mutations) or "none"
    print(f"{status:4} {label:14} mutations={mutation_label} stage={trial.stage}")
    print(f"     events={list(trial.events)}")
    print(f"     replay={'ready' if trial.replay_available else 'not-ready'}")
    if trial.error:
        print(f"     error={trial.error}")


def campaign_conditions() -> Iterable[tuple[str, ...]]:
    for perturbation in PERTURBATIONS:
        yield (perturbation,)
    yield from itertools.combinations(PERTURBATIONS, 2)


async def find_first_failure(solari: Solari, shop_url: str) -> tuple[str, ...] | None:
    for index, mutations in enumerate(campaign_conditions(), start=1):
        condition = tuple(mutations)
        trial = await run_trial(solari, shop_url, condition)
        print_trial(f"campaign-{index}", condition, trial)
        if not trial.passed:
            return condition
    return None


async def minimum_cardinality_failure(
    solari: Solari,
    shop_url: str,
    failing: tuple[str, ...],
) -> tuple[str, ...]:
    if len(failing) <= 1:
        return failing

    for size in range(1, len(failing)):
        for candidate in itertools.combinations(failing, size):
            trial = await run_trial(solari, shop_url, tuple(candidate))
            print_trial("minimize", tuple(candidate), trial)
            if not trial.passed:
                return tuple(candidate)
    return failing


async def confirm_failure(
    solari: Solari,
    shop_url: str,
    minimum: tuple[str, ...],
) -> tuple[bool, list[Trial]]:
    confirmations: list[Trial] = []
    for index in range(1, CONFIRMATION_RUNS + 1):
        trial = await run_trial(solari, shop_url, minimum)
        confirmations.append(trial)
        print_trial(f"confirm-{index}", minimum, trial)
    return all(not trial.passed for trial in confirmations), confirmations


async def main() -> None:
    solari_key = os.environ.get("SOLARI_API_KEY")
    if not solari_key:
        raise RuntimeError("SOLARI_API_KEY is required")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")

    print("Agent Crash Lab — M1B frozen adversarial campaign")
    print(f"model={MODEL}")
    print(f"frozen_perturbations={list(PERTURBATIONS)}")
    print("campaign=baseline -> singles -> pairs -> minimum-cardinality search -> 2 confirmations")

    async with SandboxClient(api_key=solari_key, base_url=BASE_URL) as sandboxes:
        sandbox = await sandboxes.create(template="base")
        try:
            await sandbox.connect()
            await sandbox.files.write("/tmp/chaosshop_m1b.py", CHAOSSHOP_SERVER)
            await sandbox.commands.run(
                "sh",
                args=["-c", "nohup python3 /tmp/chaosshop_m1b.py >/tmp/chaosshop-m1b.log 2>&1 &"],
            )
            preview = await sandbox.preview_url(PORT)
            if not isinstance(preview, dict) or not isinstance(preview.get("url"), str):
                raise RuntimeError(
                    f"Unexpected Solari preview_url response type: {type(preview).__name__}"
                )
            shop_url = preview["url"]
            print("target=<Solari preview URL redacted>")

            async with Solari(api_key=solari_key) as solari:
                baseline = await run_trial(solari, shop_url, ())
                print_trial("baseline", (), baseline)
                if not baseline.passed:
                    print("\nM1B INVALID")
                    print("Clean baseline failed; adversarial campaign was not executed.")
                    return

                failing = await find_first_failure(solari, shop_url)
                if failing is None:
                    print("\nM1B INCONCLUSIVE")
                    print("Baseline passed and every frozen single/pair condition passed.")
                    print("Do not strengthen or tune frozen perturbations after this result.")
                    return

                print("\nObjective failure found. Searching for minimum-cardinality breaking condition...")
                minimum = await minimum_cardinality_failure(solari, shop_url, failing)
                print(f"candidate_minimum={','.join(minimum)}")

                reproduced, confirmations = await confirm_failure(solari, shop_url, minimum)
                if reproduced:
                    event_signatures = {tuple(trial.events) for trial in confirmations}
                    if len(event_signatures) == 1:
                        print("\nM1B PROVED")
                        print(f"minimum_breaking_condition={','.join(minimum)}")
                        print(f"confirmation_failures={CONFIRMATION_RUNS}/{CONFIRMATION_RUNS}")
                        print("confirmation_event_outcome=consistent")
                    else:
                        print("\nM1B NOT YET PROVED")
                        print("Minimum condition failed twice, but confirmation event outcomes differed.")
                        print("Preserve evidence; do not retune the frozen perturbations.")
                else:
                    failed_count = sum(not trial.passed for trial in confirmations)
                    print("\nM1B NOT YET PROVED")
                    print(
                        f"Minimum candidate reproduced objective failure {failed_count}/{CONFIRMATION_RUNS} times."
                    )
                    print("Preserve evidence; do not retune the frozen perturbations.")
        finally:
            await sandbox.kill()


if __name__ == "__main__":
    asyncio.run(main())
