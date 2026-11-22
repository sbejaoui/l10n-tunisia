# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingPaymentReception(WithholdingTaxTestCommon):
    def _register_withholding(self, move):
        journal = (
            self.inbound_withholding_journal
            if move.move_type == "out_invoice"
            else self.withholding_journal
        )
        wizard = self._create_payment_wizard(move)
        with Form(wizard) as form:
            form.journal_id = journal
        return wizard._create_payments()

    def _check_certificate_flow(self, move_type):
        invoice = self._create_move(self.product_a, 2000, move_type=move_type)
        payment = self._register_withholding(invoice)

        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)
        self.assertTrue(payment.is_reconciled)
        self.assertFalse(payment.withholding_reception_confirmed)
        self.assertAlmostEqual(
            invoice.amount_residual, invoice.amount_total - payment.amount
        )
        self.assertNotIn(
            payment.journal_id,
            self._create_payment_wizard(invoice).available_journal_ids,
        )

        bank_journal = self.company_data["default_journal_bank"]
        methods = (
            bank_journal.inbound_payment_method_line_ids
            if payment.payment_type == "inbound"
            else bank_journal.outbound_payment_method_line_ids
        )
        methods.payment_account_id = bank_journal.default_account_id
        balance_wizard = self._create_payment_wizard(invoice)
        with Form(balance_wizard) as form:
            form.journal_id = bank_journal
        balance_payment = balance_wizard._create_payments()

        self.assertTrue(balance_payment.is_matched)
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(invoice.payment_state, "in_payment")
        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)
        journal_entry = payment.move_id
        journal_items = journal_entry.line_ids

        # standard validation must follow certificate confirmation too
        payment.action_validate()

        self.assertEqual(payment.state, "paid")
        self.assertTrue(payment.is_matched)
        self.assertTrue(payment.withholding_reception_confirmed)
        self.assertTrue(payment.withholding_reception_date)
        self.assertEqual(payment.withholding_reception_user_id, self.env.user)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(payment.move_id, journal_entry)
        self.assertEqual(payment.move_id.line_ids, journal_items)

    def test_incoming_certificate_reception(self):
        self._check_certificate_flow("out_invoice")

    def test_outgoing_certificate_delivery(self):
        self._check_certificate_flow("in_invoice")

    def test_reset_clears_confirmation_and_requires_revalidation(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        payment.action_validate_withholding()

        payment.action_draft()

        self.assertEqual(payment.state, "draft")
        self.assertFalse(payment.withholding_reception_confirmed)
        self.assertFalse(payment.withholding_reception_user_id)
        self.assertFalse(payment.withholding_reception_date)
        self.assertFalse(payment.is_matched)
        payment.action_post()
        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)

    def test_batch_validation_and_duplicate_validation(self):
        first_invoice = self._create_move(self.product_a, 2000)
        second_invoice = self._create_move(self.product_a, 3000)
        payments = self._register_withholding(first_invoice)
        payments |= self._register_withholding(second_invoice)

        payments.action_validate_withholding()

        self.assertEqual(payments.mapped("state"), ["paid", "paid"])
        self.assertTrue(all(payments.mapped("is_matched")))
        with self.assertRaises(UserError):
            payments.action_validate_withholding()

    def test_draft_certificate_cannot_be_validated(self):
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.withholding_journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": 30,
            }
        )
        with self.assertRaises(UserError):
            payment.action_validate_withholding()

    def test_standalone_foreign_withholding_payment_is_rejected(self):
        self.partner_a.country_id = self.env.ref("base.fr")
        with self.assertRaises(ValidationError):
            self.env["account.payment"].create(
                {
                    "journal_id": self.withholding_journal.id,
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": self.partner_a.id,
                    "amount": 30,
                }
            )

    def test_country_change_before_posting_withholding_is_rejected(self):
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.withholding_journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": 30,
            }
        )
        self.partner_a.country_id = self.env.ref("base.fr")
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_direct_withholding_refund_is_rejected(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        for partner_type, direction in (
            ("customer", "outbound"),
            ("supplier", "inbound"),
        ):
            with self.subTest(partner_type=partner_type, direction=direction):
                with (
                    self.assertRaisesRegex(ValidationError, "refunds"),
                    self.cr.savepoint(),
                ):
                    self.env["account.payment"].create(
                        {
                            "journal_id": journal.id,
                            "partner_id": self.partner_a.id,
                            "partner_type": partner_type,
                            "payment_type": direction,
                            "amount": 30,
                        }
                    )

    def test_refund_document_cannot_be_hidden_by_payment_direction(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        for move_type, partner_type, direction in (
            ("out_refund", "customer", "inbound"),
            ("in_refund", "supplier", "outbound"),
        ):
            with self.subTest(move_type=move_type):
                refund = self._create_move(self.product_a, 2000, move_type=move_type)
                with (
                    self.assertRaisesRegex(ValidationError, "refunds"),
                    self.cr.savepoint(),
                ):
                    self.env["account.payment"].create(
                        {
                            "journal_id": journal.id,
                            "partner_id": self.partner_a.id,
                            "partner_type": partner_type,
                            "payment_type": direction,
                            "invoice_ids": [Command.set(refund.ids)],
                            "amount": 30,
                        }
                    )

    def test_payment_direction_cannot_be_changed_to_a_withholding_refund(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        payment = self.env["account.payment"].create(
            {
                "journal_id": journal.id,
                "partner_id": self.partner_a.id,
                "partner_type": "customer",
                "payment_type": "inbound",
                "amount": 30,
            }
        )
        with (
            self.assertRaisesRegex(ValidationError, "refunds"),
            self.cr.savepoint(),
        ):
            payment.payment_type = "outbound"

    def test_inactive_states_cannot_keep_certificate_confirmation_via_orm(self):
        for state in ("draft", "canceled", "rejected"):
            with self.subTest(state=state):
                with (
                    self.assertRaisesRegex(
                        ValidationError, "cannot retain certificate"
                    ),
                    self.cr.savepoint(),
                ):
                    self.env["account.payment"].create(
                        {
                            "journal_id": self.withholding_journal.id,
                            "payment_type": "outbound",
                            "partner_type": "supplier",
                            "partner_id": self.partner_a.id,
                            "amount": 30,
                            "state": state,
                            "withholding_reception_confirmed": True,
                        }
                    )

    def test_lifecycle_actions_clear_certificate_confirmation(self):
        for action in ("action_draft", "action_cancel", "action_reject"):
            with self.subTest(action=action):
                invoice = self._create_move(self.product_a, 2000)
                payment = self._register_withholding(invoice)
                payment.action_validate_withholding()
                getattr(payment, action)()
                self.assertFalse(payment.withholding_reception_confirmed)
                self.assertFalse(payment.withholding_reception_date)
                self.assertFalse(payment.withholding_reception_user_id)

    def test_direct_state_change_cannot_keep_confirmed_certificate(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        payment.action_validate_withholding()
        with (
            self.assertRaisesRegex(ValidationError, "cannot retain certificate"),
            self.cr.savepoint(),
        ):
            payment.state = "draft"
        self.assertTrue(payment.withholding_reception_confirmed)
