from __future__ import annotations

import asyncio
import math
import os
from collections import Counter
from dataclasses import dataclass
from typing import Awaitable, Callable

from solari_browser import Solari
from solari_sandbox import SandboxClient

from m1b_campaign import CampaignInfrastructureError, execute_trial, failure_class
from m1b_live import BASE_URL, CHAOSSHOP_SERVER, MODEL, PORT, Trial

VALID_TRIALS = 20
CONDITION = ("review_rollback",)
WILSON_Z = 1.959963984540054
# Solari preview capabilities expire after roughly an hour. Renew between trials
# so a long characterization does not become permanently infrastructure-invalid.
PREVIEW_RENEWAL_SECONDS = 45 * 60


@dataclass(frozen=True)
class Characterization:
    valid_trials: int
    invalid_attempts: int
    passes: int
    failures: int
    failure_classes: dict[str, int]
    failure_rate: float
    recovery_rate: float
    failure_interval: tuple[float, float]


def wilson_interval(successes: int, trials: int, z: float = WILSON_Z) -> tuple[float, float]:
    if trials <= 0:
        raise ValueError("trials must be positive")
    if successes < 0 or successes > trials:
        raise ValueError("successes must be between zero and trials")
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denominator
    margin = (
        z
        * math.sqrt((p * (1.0 - p) / trials) + (z2 / (4.0 * trials * trials)))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def summarize(trials: list[Trial], invalid_attempts: int) -> Characterization:
    if len(trials) != VALID_TRIALS:
        raise ValueError(f"expected exactly {VALID_TRIALS} valid trials")
    failures = [trial for trial in trials if not trial.passed]
    failure_count = len(failures)
    pass_count = len(trials) - failure_count
    classes = Counter(failure_class(trial) for trial in failures)
    interval = wilson_interval(failure_count, len(trials))
    return Characterization(
        valid_trials=len(trials),
        invalid_attempts=invalid_attempts,
        passes=pass_count,
        failures=failure_count,
        failure_classes=dict(sorted(classes.items())),
        failure_rate=failure_count / len(trials),
        recovery_rate=pass_count / len(trials),
        failure_interval=interval,
    )


def print_trial(index: int, trial: Trial) -> None:
    status = "PASS" if trial.passed else "FAIL"
    print(f"{status:4} trial-{index:02d} condition=review_rollback stage={trial.stage}")
    print(f"     failure_class={failure_class(trial)}")
    print(f"     events={list(trial.events)}")
    print("     replay=ready")


async def collect_valid_trials(
    solari: Solari,
    initial_shop_url: str,
    renew_preview: Callable[[], Awaitable[str]],
    *,
    monotonic: Callable[[], float] | None = None,
) -> tuple[list[Trial], int]:
    clock = monotonic or asyncio.get_running_loop().time
    valid: list[Trial] = []
    invalid_attempts = 0
    attempt = 0
    shop_url = initial_shop_url
    preview_minted_at = clock()

    while len(valid) < VALID_TRIALS:
        if clock() - preview_minted_at >= PREVIEW_RENEWAL_SECONDS:
            shop_url = await renew_preview()
            preview_minted_at = clock()
            print("PREVIEW renewed between trials (credential redacted)")

        attempt += 1
        ordinal = len(valid) + 1
        try:
            trial = await execute_trial(solari, shop_url, CONDITION)
        except CampaignInfrastructureError as exc:
            invalid_attempts += 1
            print(f"INVALID attempt-{attempt:02d}: {exc}")
            print("        excluded from 20 valid trials; renewing preview and retrying same ordinal")
            shop_url = await renew_preview()
            preview_minted_at = clock()
            continue
        valid.append(trial)
        print_trial(ordinal, trial)
    return valid, invalid_attempts


def print_summary(summary: Characterization) -> None:
    low, high = summary.failure_interval
    print("\nM1C CHARACTERIZED")
    print(f"model={MODEL}")
    print("condition=review_rollback")
    print(f"valid_trials={summary.valid_trials}")
    print(f"invalid_infrastructure_attempts={summary.invalid_attempts}")
    print(f"recoveries={summary.passes}")
    print(f"failures={summary.failures}")
    print(f"recovery_rate={summary.recovery_rate:.1%}")
    print(f"failure_rate={summary.failure_rate:.1%}")
    print(f"failure_classes={summary.failure_classes}")
    print(f"failure_probability_wilson_95=[{low:.3f}, {high:.3f}]")
    print("Interpret only for this frozen agent/task/environment configuration.")


async def main() -> None:
    solari_key = os.environ.get("SOLARI_API_KEY")
    if not solari_key:
        raise RuntimeError("SOLARI_API_KEY is required")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")

    print("Agent Crash Lab — M1C frozen repeated reliability characterization")
    print(f"model={MODEL}")
    print("condition=review_rollback")
    print(f"valid_trial_target={VALID_TRIALS}")
    print("target=<Solari preview URL redacted>")

    async with SandboxClient(api_key=solari_key, base_url=BASE_URL) as sandboxes:
        sandbox = await sandboxes.create(template="base")
        try:
            await sandbox.connect()
            await sandbox.files.write("/tmp/chaosshop_m1c.py", CHAOSSHOP_SERVER)
            await sandbox.commands.run(
                "sh",
                args=["-c", "nohup python3 /tmp/chaosshop_m1c.py >/tmp/chaosshop-m1c.log 2>&1 &"],
            )

            async def renew_preview() -> str:
                preview = await sandbox.preview_url(PORT)
                if not isinstance(preview, dict) or not isinstance(preview.get("url"), str):
                    raise CampaignInfrastructureError(
                        f"unexpected preview response type ({type(preview).__name__})"
                    )
                return preview["url"]

            shop_url = await renew_preview()

            async with Solari(api_key=solari_key) as solari:
                valid, invalid_attempts = await collect_valid_trials(
                    solari,
                    shop_url,
                    renew_preview,
                )
                print_summary(summarize(valid, invalid_attempts))
        except CampaignInfrastructureError as exc:
            print("\nM1C INVALID/ABORTED")
            print(f"Experiment could not complete validly: {exc}")
        finally:
            await sandbox.kill()


if __name__ == "__main__":
    asyncio.run(main())
