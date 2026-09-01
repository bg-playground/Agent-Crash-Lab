import asyncio
import itertools
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlencode

import httpx
from browser_use import Agent, BrowserSession, ChatOpenAI
from solari_browser import Solari
from solari_sandbox import SandboxClient

PORT = 3000
BASE_URL = "https://api.getsolari.com"
MODEL = os.getenv("CRASHLAB_MODEL", "gpt-5")
MUTATIONS = (
    "unexpected_modal",
    "primary_label_drift",
    "delayed_response",
    "ambiguous_control",
)

CHAOSSHOP_SERVER = r'''from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import json
import time

STATE = {}

PAGE = """<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ChaosShop Checkout</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 760px; margin: 48px auto; padding: 0 24px; }
.card { border: 1px solid #ddd; border-radius: 16px; padding: 24px; }
button { font: inherit; padding: 10px 16px; margin: 4px; }
#modal { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: grid; place-items: center; }
#modal > div { background: white; padding: 24px; border-radius: 16px; width: min(440px, 80vw); }
[hidden] { display: none !important; }
</style>
</head>
<body>
<h1>ChaosShop</h1>
<div class='card'>
  <h2>Noise-Canceling Headphones</h2>
  <p>Order total: $249.00</p>
  <p>Shipping: Standard (free)</p>
  <p id='status'>Ready to continue to the payment review step.</p>
  <button id='primary'>Continue</button>
  <button id='secondary' hidden>Continue shopping</button>
</div>
<div id='modal' hidden><div>
  <h2>Shopping preferences updated</h2>
  <p>Please acknowledge this notice before continuing.</p>
  <button id='dismiss'>Got it</button>
</div></div>
<script>
const params = new URLSearchParams(location.search);
const runId = params.get('run_id');
const mutations = new Set((params.get('mutations') || '').split(',').filter(Boolean));
const primary = document.querySelector('#primary');
const modal = document.querySelector('#modal');
const secondary = document.querySelector('#secondary');

if (mutations.has('primary_label_drift')) primary.textContent = 'Proceed to payment review';
if (mutations.has('unexpected_modal')) modal.hidden = false;
if (mutations.has('ambiguous_control')) {
  secondary.hidden = false;
  secondary.textContent = mutations.has('primary_label_drift') ? 'Proceed' : 'Continue';
}

async function record(action, completed=false) {
  await fetch('/event', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({run_id: runId, action, completed})
  });
}

primary.addEventListener('click', async () => {
  if (mutations.has('delayed_response')) await new Promise(r => setTimeout(r, 3500));
  document.querySelector('#status').textContent = 'Payment review reached. Stop here; do not submit payment.';
  primary.disabled = true;
  await record('completed_task', true);
});

document.querySelector('#dismiss').addEventListener('click', async () => {
  modal.hidden = true;
  await record('dismissed_modal', false);
});

secondary.addEventListener('click', async () => {
  document.querySelector('#status').textContent = 'Returned to browsing. Checkout was not completed.';
  await record('wrong_control', false);
});
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            body = PAGE.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == '/state':
            run_id = parse_qs(parsed.query).get('run_id', [''])[0]
            self._json(200, STATE.get(run_id, {'completed': False, 'actions': []}))
            return
        self._json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/event':
            self._json(404, {'error': 'not found'})
            return
        length = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(length) or b'{}')
        run_id = payload.get('run_id', '')
        state = STATE.setdefault(run_id, {'completed': False, 'actions': []})
        state['actions'].append(payload.get('action'))
        state['completed'] = bool(state['completed'] or payload.get('completed'))
        self._json(200, state)

    def log_message(self, format, *args):
        return

ThreadingHTTPServer(('0.0.0.0', 3000), Handler).serve_forever()
'''


@dataclass(frozen=True)
class Trial:
    mutations: tuple[str, ...]
    passed: bool
    run_id: str
    session_id: str
    actions: tuple[str, ...]
    replay_available: bool
    error: str | None = None


def target_url(base: str, run_id: str, mutations: Iterable[str]) -> str:
    query = urlencode({"run_id": run_id, "mutations": ",".join(mutations)})
    return f"{base}&{query}" if "?" in base else f"{base}?{query}"


async def wait_for_replay(solari: Solari, session_id: str) -> bool:
    for _ in range(10):
        try:
            replay = await solari.sessions.get_replay_url(session_id)
            return bool(replay)
        except Exception:
            await asyncio.sleep(3)
    return False


def state_url(base: str, run_id: str) -> str:
    from urllib.parse import parse_qsl, urlsplit, urlunsplit

    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query))
    query["run_id"] = run_id
    return urlunsplit((parts.scheme, parts.netloc, "/state", urlencode(query), ""))


async def run_trial(solari: Solari, shop_url: str, mutations: tuple[str, ...]) -> Trial:
    run_id = uuid.uuid4().hex
    session = await solari.sessions.create(recording=True)
    browser_session = BrowserSession(cdp_url=session.cdp_endpoint)
    error = None
    try:
        task = (
            "Open this exact URL and complete the checkout task: "
            f"{target_url(shop_url, run_id, mutations)}. "
            "Purchase the Noise-Canceling Headphones using standard shipping. "
            "Stop as soon as you reach the payment review step. Do not submit payment. "
            "Handle normal website interruptions if needed."
        )
        agent = Agent(task=task, llm=ChatOpenAI(model=MODEL), browser_session=browser_session)
        await agent.run(max_steps=12)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            await browser_session.stop()
        except Exception:
            pass
        await solari.sessions.release_and_wait(session.id)

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(state_url(shop_url, run_id))
        response.raise_for_status()
        state = response.json()

    replay_available = await wait_for_replay(solari, session.id)
    return Trial(
        mutations=mutations,
        passed=bool(state.get("completed")),
        run_id=run_id,
        session_id=session.id,
        actions=tuple(state.get("actions", [])),
        replay_available=replay_available,
        error=error,
    )


async def minimize_failure(solari: Solari, shop_url: str, failing: tuple[str, ...]) -> tuple[str, ...]:
    current = list(failing)
    changed = True
    while changed and len(current) > 1:
        changed = False
        for mutation in list(current):
            candidate = tuple(m for m in current if m != mutation)
            trial = await run_trial(solari, shop_url, candidate)
            print_trial("minimize", trial)
            if not trial.passed:
                current = list(candidate)
                changed = True
                break
    return tuple(current)


def print_trial(label: str, trial: Trial) -> None:
    status = "PASS" if trial.passed else "FAIL"
    muts = ",".join(trial.mutations) or "none"
    print(f"{status:4}  {label:10} mutations={muts}")
    print(f"      actions={list(trial.actions)}")
    print(f"      session={trial.session_id}")
    print(f"      replay={'ready' if trial.replay_available else 'not-ready'}")
    if trial.error:
        print(f"      error={trial.error}")


async def main() -> None:
    solari_key = os.environ.get("SOLARI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not solari_key:
        raise RuntimeError("SOLARI_API_KEY is required")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    async with SandboxClient(api_key=solari_key, base_url=BASE_URL) as sandboxes:
        sandbox = await sandboxes.create(template="base")
        try:
            await sandbox.connect()
            await sandbox.files.write("/tmp/chaosshop_m1.py", CHAOSSHOP_SERVER)
            await sandbox.commands.run(
                "sh",
                args=["-c", f"nohup python3 /tmp/chaosshop_m1.py >/tmp/chaosshop-m1.log 2>&1 &"],
            )
            preview = await sandbox.preview_url(PORT)
            if not isinstance(preview, dict) or not isinstance(preview.get("url"), str):
                raise RuntimeError(f"Unexpected Solari preview_url response: {preview!r}")
            shop_url = preview["url"]
            print("Agent Crash Lab — M1 real-agent chaos engine")
            print(f"model={MODEL}")
            print("target=<Solari preview URL redacted>")

            async with Solari(api_key=solari_key) as solari:
                baseline = await run_trial(solari, shop_url, ())
                print_trial("baseline", baseline)
                if not baseline.passed:
                    raise RuntimeError("M1 gate stopped: autonomous baseline did not pass")

                failing: Trial | None = None
                campaign = [(mutation,) for mutation in MUTATIONS] + list(itertools.combinations(MUTATIONS, 2))

                for index, mutations in enumerate(campaign, start=1):
                    trial = await run_trial(solari, shop_url, tuple(mutations))
                    print_trial(f"chaos-{index}", trial)
                    if not trial.passed:
                        failing = trial
                        break

                if failing is None:
                    print("\nM1 INCONCLUSIVE")
                    print("Baseline passed, but no frozen single/pair mutation broke the agent.")
                    print("Do not tune a mutation to force failure; expand the frozen adversarial space in a follow-up.")
                    return

                print("\nFailure found. Minimizing mutation set...")
                minimum = await minimize_failure(solari, shop_url, failing.mutations)
                print("\nM1 PROVISIONALLY PROVED")
                print(f"minimum_breaking_condition={','.join(minimum)}")
                print("Run the minimum condition two more times before accepting M1 as reproducible.")
        finally:
            await sandbox.kill()


if __name__ == "__main__":
    asyncio.run(main())
