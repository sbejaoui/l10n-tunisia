# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingPaymentReception(WithholdingTaxTestCommon):
    def _register_withholding(self, move):
        wizard = self._create_payment_wizard(move)
        with Form(wizard) as form:
            form.journal_id = self.withholding_journal
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
            self.withholding_journal,
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
            {"journal_id": self.withholding_journal.id, "amount": 30}
        )
        with self.assertRaises(UserError):
            payment.action_validate_withholding()
