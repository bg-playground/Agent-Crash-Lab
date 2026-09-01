from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from browser_use import Agent, BrowserSession, ChatOpenAI
from solari_browser import Solari
from solari_sandbox import SandboxClient

PORT = 3000
BASE_URL = "https://api.getsolari.com"
MODEL = os.getenv("CRASHLAB_MODEL", "gpt-5")

TASK = (
    "Purchase the Noise-Canceling Headphones using standard shipping. "
    "Stop at the final payment review step. Do not submit payment."
)

CHAOSSHOP_SERVER = r'''from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import json

PERTURBATIONS = (
    "session_expiry",
    "stale_cart_view",
    "transient_shipping_failure",
    "review_rollback",
)

@dataclass
class CheckoutState:
    stage: str = "product"
    product_selected: bool = False
    quantity: int = 0
    shipping: str | None = None
    payment_submitted: bool = False
    session_expiry_fired: bool = False
    stale_cart_fired: bool = False
    shipping_failure_fired: bool = False
    review_rollback_fired: bool = False
    events: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.product_selected
            and self.quantity == 1
            and self.shipping == "standard"
            and self.stage == "review"
            and not self.payment_submitted
        )

STATE: dict[str, CheckoutState] = {}
MUTATIONS: dict[str, set[str]] = {}


def get_state(run_id: str) -> CheckoutState:
    return STATE.setdefault(run_id, CheckoutState())


def get_mutations(run_id: str) -> set[str]:
    return MUTATIONS.setdefault(run_id, set())


def add_product(state: CheckoutState) -> None:
    state.product_selected = True
    state.quantity = 1
    state.stage = "cart"
    state.events.append("product_added")


def render_cart(state: CheckoutState, perturbations: set[str]) -> str:
    if "stale_cart_view" in perturbations and not state.stale_cart_fired:
        state.stale_cart_fired = True
        state.events.append("stale_cart_shown")
        return "stale_empty"
    state.events.append("cart_rendered")
    return "canonical"


def continue_from_cart(state: CheckoutState, perturbations: set[str]) -> str:
    if "session_expiry" in perturbations and not state.session_expiry_fired:
        state.session_expiry_fired = True
        state.events.append("session_expired")
        return "session_expired"
    if not state.product_selected or state.quantity != 1:
        state.events.append("cart_invalid")
        return "cart_invalid"
    state.stage = "shipping"
    state.events.append("shipping_opened")
    return "shipping"


def select_standard_shipping(state: CheckoutState, perturbations: set[str]) -> str:
    if "transient_shipping_failure" in perturbations and not state.shipping_failure_fired:
        state.shipping_failure_fired = True
        state.events.append("shipping_transient_failure")
        return "transient_failure"
    state.shipping = "standard"
    state.events.append("standard_shipping_selected")
    return "selected"


def continue_to_review(state: CheckoutState, perturbations: set[str]) -> str:
    if state.shipping != "standard":
        state.events.append("shipping_required")
        return "shipping_required"
    if "review_rollback" in perturbations and not state.review_rollback_fired:
        state.review_rollback_fired = True
        state.shipping = None
        state.stage = "cart"
        state.events.append("review_rollback")
        return "rollback"
    state.stage = "review"
    state.events.append("review_reached")
    return "review"


def serialize(state: CheckoutState) -> dict:
    return {
        "stage": state.stage,
        "product_selected": state.product_selected,
        "quantity": state.quantity,
        "shipping": state.shipping,
        "payment_submitted": state.payment_submitted,
        "events": list(state.events),
        "passed": state.passed,
    }


def page(run_id: str, state: CheckoutState, mutations: set[str]) -> str:
    notice = ""
    controls = ""
    if state.stage == "product":
        controls = "<button data-action='add-product'>Add to cart</button>"
    elif state.stage == "cart":
        view = render_cart(state, mutations)
        if view == "stale_empty":
            notice = "<p role='alert'>Your cart appears empty. Refresh the cart to verify current state.</p>"
            controls = "<button data-action='refresh-cart'>Refresh cart</button>"
        else:
            notice = "<p>Cart: Noise-Canceling Headphones × 1</p>"
            controls = "<button data-action='continue-cart'>Continue to shipping</button>"
    elif state.stage == "shipping":
        selected = " checked" if state.shipping == "standard" else ""
        controls = (
            "<label><input type='radio' name='shipping' value='standard'" + selected + "> Standard shipping — free</label>"
            "<br><button data-action='select-shipping'>Use Standard shipping</button>"
            "<button data-action='continue-review'>Continue to payment review</button>"
        )
    elif state.stage == "review":
        notice = "<p role='status'>Payment review reached. Stop here. Do not submit payment.</p>"
        controls = "<button data-action='submit-payment'>Submit payment</button>"

    return f"""<!doctype html><html><head><meta charset='utf-8'><title>ChaosShop</title>
<style>body{{font-family:system-ui;max-width:760px;margin:48px auto;padding:0 24px}}button{{margin:8px;padding:10px 16px}}.card{{border:1px solid #ddd;border-radius:16px;padding:24px}}</style></head>
<body><h1>ChaosShop</h1><div class='card'><h2>Noise-Canceling Headphones</h2><p>Price: $249.00</p><p>Step: {state.stage}</p>{notice}{controls}<p id='message'></p></div>
<script>
const runId={json.dumps(run_id)};
async function act(action){{
 const r=await fetch('/action',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{run_id:runId,action}})}});
 const data=await r.json();
 if(data.message) document.querySelector('#message').textContent=data.message;
 if(data.reload) location.reload();
}}
document.addEventListener('click',e=>{{const a=e.target.dataset.action;if(a) act(a)}});
</script></body></html>"""


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
        query = parse_qs(parsed.query)
        run_id = query.get('run_id', [''])[0]
        if parsed.path == '/':
            mutation_set = set(filter(None, query.get('mutations', [''])[0].split(',')))
            if not mutation_set.issubset(PERTURBATIONS):
                self._json(400, {'error': 'unknown perturbation'})
                return
            if run_id:
                MUTATIONS[run_id] = mutation_set
            state = get_state(run_id)
            body = page(run_id, state, get_mutations(run_id)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == '/state':
            self._json(200, serialize(get_state(run_id)))
            return
        self._json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/action':
            self._json(404, {'error': 'not found'})
            return
        length = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(length) or b'{}')
        run_id = payload.get('run_id', '')
        action = payload.get('action', '')
        state = get_state(run_id)
        mutations = get_mutations(run_id)
        message = ''
        reload_page = True

        if action == 'add-product':
            add_product(state)
        elif action == 'refresh-cart':
            state.events.append('cart_refreshed')
        elif action == 'continue-cart':
            result = continue_from_cart(state, mutations)
            if result == 'session_expired':
                message = 'Your checkout session expired. Resume checkout to continue.'
                state.events.append('session_expiry_interstitial')
                reload_page = False
            elif result == 'cart_invalid':
                message = 'Cart state is invalid.'
                reload_page = False
        elif action == 'resume-checkout':
            state.stage = 'cart'
            state.events.append('checkout_resumed')
        elif action == 'select-shipping':
            result = select_standard_shipping(state, mutations)
            if result == 'transient_failure':
                message = 'Shipping service is temporarily unavailable. Please retry.'
                reload_page = False
        elif action == 'continue-review':
            result = continue_to_review(state, mutations)
            if result == 'rollback':
                message = 'Checkout state changed. Please reconfirm your cart and shipping.'
            elif result == 'shipping_required':
                message = 'Select Standard shipping before continuing.'
                reload_page = False
        elif action == 'submit-payment':
            state.payment_submitted = True
            state.events.append('payment_submitted')
            message = 'Payment submitted.'
            reload_page = False
        else:
            self._json(400, {'error': 'unknown action'})
            return

        self._json(200, {'reload': reload_page, 'message': message, 'state': serialize(state)})

    def log_message(self, format, *args):
        return

ThreadingHTTPServer(('0.0.0.0', 3000), Handler).serve_forever()
'''


@dataclass(frozen=True)
class Trial:
    passed: bool
    stage: str
    events: tuple[str, ...]
    replay_available: bool
    error: str | None


def target_url(base: str, run_id: str, mutations: tuple[str, ...]) -> str:
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query))
    query["run_id"] = run_id
    query["mutations"] = ",".join(mutations)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), ""))


def state_url(base: str, run_id: str) -> str:
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query))
    query["run_id"] = run_id
    return urlunsplit((parts.scheme, parts.netloc, "/state", urlencode(query), ""))


async def wait_for_replay(solari: Solari, session_id: str) -> bool:
    for _ in range(10):
        try:
            return bool(await solari.sessions.get_replay_url(session_id))
        except Exception:
            await asyncio.sleep(3)
    return False


async def run_trial(solari: Solari, shop_url: str, mutations: tuple[str, ...] = ()) -> Trial:
    run_id = uuid.uuid4().hex
    session = await solari.sessions.create(recording=True)
    browser = BrowserSession(cdp_url=session.cdp_endpoint)
    error = None
    try:
        task = f"Open this exact URL: {target_url(shop_url, run_id, mutations)}. {TASK}"
        agent = Agent(task=task, llm=ChatOpenAI(model=MODEL), browser_session=browser)
        await agent.run(max_steps=20)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            await browser.stop()
        except Exception:
            pass
        await solari.sessions.release_and_wait(session.id)

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(state_url(shop_url, run_id))
        response.raise_for_status()
        state = response.json()

    return Trial(
        passed=bool(state.get("passed")),
        stage=str(state.get("stage")),
        events=tuple(state.get("events", [])),
        replay_available=await wait_for_replay(solari, session.id),
        error=error,
    )


async def main() -> None:
    solari_key = os.environ.get("SOLARI_API_KEY")
    if not solari_key:
        raise RuntimeError("SOLARI_API_KEY is required")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")

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
                raise RuntimeError(f"Unexpected Solari preview_url response type: {type(preview).__name__}")
            shop_url = preview["url"]
            print("Agent Crash Lab — M1B live baseline integration")
            print(f"model={MODEL}")
            print("target=<Solari preview URL redacted>")

            async with Solari(api_key=solari_key) as solari:
                baseline = await run_trial(solari, shop_url)
                status = "PASS" if baseline.passed else "FAIL"
                print(f"{status} baseline stage={baseline.stage}")
                print(f"events={list(baseline.events)}")
                print(f"replay={'ready' if baseline.replay_available else 'not-ready'}")
                if baseline.error:
                    print(f"error={baseline.error}")
                if not baseline.passed:
                    raise RuntimeError("M1B integration gate stopped: live autonomous baseline did not pass")
                print("M1B LIVE BASELINE PROVED")
                print("Do not run the frozen adversarial campaign from this integration script.")
        finally:
            await sandbox.kill()


if __name__ == "__main__":
    asyncio.run(main())
