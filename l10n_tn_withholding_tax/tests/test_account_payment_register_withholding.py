# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentRegisterWithholding(WithholdingTaxTestCommon):
    # Purpose: only withholding journals linked to an applicable rule are selectable.
    def test_available_journals_follow_applicable_rules(self):
        eligible_bill = self._create_move(self.product_a, 2000)
        unruled_bill = self._create_move(self.unruled_product, 2000)

        eligible_wizard = self._create_payment_wizard(eligible_bill)
        unruled_wizard = self._create_payment_wizard(unruled_bill)

        self.assertIn(self.withholding_journal, eligible_wizard.available_journal_ids)
        self.assertNotIn(
            self.other_withholding_journal, eligible_wizard.available_journal_ids
        )
        self.assertNotIn(self.withholding_journal, unruled_wizard.available_journal_ids)
        self.assertIn(
            self.company_data["default_journal_bank"],
            eligible_wizard.available_journal_ids,
        )

    # Purpose: the alert must show the rule and amount only for eligible bills.
    def test_alert_uses_only_eligible_bills(self):
        eligible_bill = self._create_move(self.product_a, 2000)
        unruled_bill = self._create_move(self.unruled_product, 2000)
        wizard = self._create_payment_wizard(eligible_bill | unruled_bill)
        expected_amount = (
            eligible_bill.amount_total * self.withholding_journal.withholding_tax_rate
        )

        self.assertIn(self.withholding_journal.name, wizard.withholding_tax_alert)
        self.assertIn(str(expected_amount), wizard.withholding_tax_alert)
        self.assertNotIn(str(expected_amount * 2), wizard.withholding_tax_alert)

    # Purpose: selecting a withholding journal must calculate from eligible bills only.
    def test_withholding_journal_amount_and_eligible_bills(self):
        eligible_bill = self._create_move(self.product_a, 2000)
        unruled_bill = self._create_move(self.unruled_product, 2000)
        wizard = self._create_payment_wizard(eligible_bill | unruled_bill)

        with Form(wizard) as form:
            form.journal_id = self.withholding_journal
            self.assertAlmostEqual(
                form.amount,
                eligible_bill.amount_total
                * self.withholding_journal.withholding_tax_rate,
            )

        self.assertEqual(wizard._get_withholding_eligible_bills(), eligible_bill)

    # Purpose: a multi-bill withholding payment must be created only for eligible bills.
    def test_multiple_bills_create_payment_only_for_eligible_bill(self):
        eligible_bill = self._create_move(self.product_a, 2000)
        unruled_bill = self._create_move(self.unruled_product, 2000)
        wizard = self._create_payment_wizard(eligible_bill | unruled_bill)

        with Form(wizard) as form:
            form.journal_id = self.withholding_journal

        payments = wizard._create_payments()

        self.assertEqual(len(payments), 1)
        self.assertEqual(payments.journal_id, self.withholding_journal)
        self.assertAlmostEqual(
            payments.amount,
            eligible_bill.amount_total * self.withholding_journal.withholding_tax_rate,
        )
        self.assertAlmostEqual(
            eligible_bill.amount_residual,
            eligible_bill.amount_total - payments.amount,
        )
        self.assertEqual(unruled_bill.amount_residual, unruled_bill.amount_total)

    # Purpose: a multi-bill withholding payment with no eligible bill must fail clearly.
    def test_multiple_bills_without_eligible_bill_raise_error(self):
        first_bill = self._create_move(self.unruled_product, 1000)
        second_bill = self._create_move(self.unruled_product, 2000)
        wizard = self._create_payment_wizard(first_bill | second_bill)
        wizard.journal_id = self.withholding_journal

        with self.assertRaises(UserError):
            wizard._create_payments()

    # Purpose: the multi-bill warning appears only for a withholding journal.
    def test_multiple_bills_warning_depends_on_selected_journal(self):
        first_bill = self._create_move(self.product_a, 1000)
        second_bill = self._create_move(self.product_a, 2000)
        wizard = self._create_payment_wizard(first_bill | second_bill)

        self.assertTrue(wizard.has_multiple_bills)
        self.assertFalse(wizard.multiple_bills_alert)

        with Form(wizard) as form:
            form.journal_id = self.withholding_journal
            self.assertTrue(form.multiple_bills_alert)

    # Purpose: a withholding payment marks the move and rule as paid.
    def test_withholding_payment_marks_rule_as_paid(self):
        bill = self._create_move(self.product_a, 2000)
        wizard = self._create_payment_wizard(bill)

        with Form(wizard) as form:
            form.journal_id = self.withholding_journal

        payments = wizard._create_payments()
        next_wizard = self._create_payment_wizard(bill)

        self.assertTrue(bill.is_rs_paid)
        self.assertTrue(bill.is_withholding_tax_rule_applied(self.withholding_rule))
        self.assertEqual(payments.journal_id, self.withholding_journal)
        self.assertFalse(next_wizard.withholding_tax_alert)
        self.assertNotIn(self.withholding_journal, next_wizard.available_journal_ids)

    # Purpose: withholding must create an inbound payment for a customer invoice.
    def test_customer_invoice_withholding_payment(self):
        invoice = self._create_move(self.product_a, 2000, move_type="out_invoice")
        wizard = self._create_payment_wizard(invoice)

        with Form(wizard) as form:
            form.journal_id = self.withholding_journal

        payment = wizard._create_payments()

        self.assertEqual(payment.payment_type, "inbound")
        self.assertEqual(payment.journal_id, self.withholding_journal)
        self.assertAlmostEqual(
            invoice.amount_residual, invoice.amount_total - payment.amount
        )

    # Purpose: selecting a journal already used for withholding must raise an error.
    def test_selecting_already_paid_withholding_journal_raises_error(self):
        bill = self._create_move(self.product_a, 2000)
        first_wizard = self._create_payment_wizard(bill)

        with Form(first_wizard) as form:
            form.journal_id = self.withholding_journal
        first_wizard._create_payments()

        second_wizard = self._create_payment_wizard(bill)
        second_wizard.journal_id = self.withholding_journal
        with self.assertRaises(UserError):
            second_wizard._check_withholding_tax_already_paid()
