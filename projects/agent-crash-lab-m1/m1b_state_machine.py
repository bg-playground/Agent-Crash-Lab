from __future__ import annotations

from dataclasses import dataclass, field

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


def refresh_cart(state: CheckoutState) -> None:
    state.events.append("cart_refreshed")


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


def resume_checkout(state: CheckoutState) -> None:
    state.stage = "cart"
    state.events.append("checkout_resumed")


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


def submit_payment(state: CheckoutState) -> None:
    state.payment_submitted = True
    state.events.append("payment_submitted")
