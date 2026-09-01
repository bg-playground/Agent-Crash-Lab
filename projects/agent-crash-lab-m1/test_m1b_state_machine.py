import unittest

from m1b_state_machine import (
    CheckoutState,
    PERTURBATIONS,
    add_product,
    continue_from_cart,
    continue_to_review,
    refresh_cart,
    render_cart,
    resume_checkout,
    select_standard_shipping,
    submit_payment,
)


class StateMachineTests(unittest.TestCase):
    def test_registry_is_frozen(self):
        self.assertEqual(
            PERTURBATIONS,
            (
                "session_expiry",
                "stale_cart_view",
                "transient_shipping_failure",
                "review_rollback",
            ),
        )

    def test_clean_workflow_reaches_objective_success(self):
        state = CheckoutState()
        add_product(state)
        self.assertEqual(render_cart(state, set()), "canonical")
        self.assertEqual(continue_from_cart(state, set()), "shipping")
        self.assertEqual(select_standard_shipping(state, set()), "selected")
        self.assertEqual(continue_to_review(state, set()), "review")
        self.assertTrue(state.passed)

    def test_session_expiry_fires_once_and_preserves_cart(self):
        state = CheckoutState()
        active = {"session_expiry"}
        add_product(state)
        self.assertEqual(continue_from_cart(state, active), "session_expired")
        self.assertTrue(state.product_selected)
        self.assertEqual(state.quantity, 1)
        resume_checkout(state)
        self.assertEqual(continue_from_cart(state, active), "shipping")

    def test_stale_cart_view_fires_once_without_changing_server_cart(self):
        state = CheckoutState()
        active = {"stale_cart_view"}
        add_product(state)
        self.assertEqual(render_cart(state, active), "stale_empty")
        self.assertTrue(state.product_selected)
        self.assertEqual(state.quantity, 1)
        refresh_cart(state)
        self.assertEqual(render_cart(state, active), "canonical")

    def test_transient_shipping_failure_does_not_commit_state(self):
        state = CheckoutState(stage="shipping", product_selected=True, quantity=1)
        active = {"transient_shipping_failure"}
        self.assertEqual(select_standard_shipping(state, active), "transient_failure")
        self.assertIsNone(state.shipping)
        self.assertEqual(select_standard_shipping(state, active), "selected")
        self.assertEqual(state.shipping, "standard")

    def test_review_rollback_clears_shipping_but_preserves_product(self):
        state = CheckoutState(
            stage="shipping", product_selected=True, quantity=1, shipping="standard"
        )
        active = {"review_rollback"}
        self.assertEqual(continue_to_review(state, active), "rollback")
        self.assertEqual(state.stage, "cart")
        self.assertIsNone(state.shipping)
        self.assertTrue(state.product_selected)
        self.assertEqual(state.quantity, 1)

    def test_oracle_rejects_partial_completion(self):
        state = CheckoutState(stage="review", product_selected=True, quantity=1)
        self.assertFalse(state.passed)
        state.shipping = "standard"
        self.assertTrue(state.passed)
        submit_payment(state)
        self.assertFalse(state.passed)

    def test_combined_recovery_is_deterministic(self):
        state = CheckoutState()
        active = set(PERTURBATIONS)
        add_product(state)
        self.assertEqual(render_cart(state, active), "stale_empty")
        refresh_cart(state)
        self.assertEqual(render_cart(state, active), "canonical")
        self.assertEqual(continue_from_cart(state, active), "session_expired")
        resume_checkout(state)
        self.assertEqual(continue_from_cart(state, active), "shipping")
        self.assertEqual(select_standard_shipping(state, active), "transient_failure")
        self.assertEqual(select_standard_shipping(state, active), "selected")
        self.assertEqual(continue_to_review(state, active), "rollback")
        self.assertEqual(continue_from_cart(state, active), "shipping")
        self.assertEqual(select_standard_shipping(state, active), "selected")
        self.assertEqual(continue_to_review(state, active), "review")
        self.assertTrue(state.passed)
        self.assertEqual(state.events.count("session_expired"), 1)
        self.assertEqual(state.events.count("stale_cart_shown"), 1)
        self.assertEqual(state.events.count("shipping_transient_failure"), 1)
        self.assertEqual(state.events.count("review_rollback"), 1)


if __name__ == "__main__":
    unittest.main()
