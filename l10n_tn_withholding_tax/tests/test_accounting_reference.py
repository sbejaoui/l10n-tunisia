# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingAccountingReference(WithholdingTaxTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data["default_journal_bank"]
        methods = (
            cls.bank_journal.inbound_payment_method_line_ids
            | cls.bank_journal.outbound_payment_method_line_ids
        )
        methods.payment_account_id = cls.bank_journal.default_account_id

    def _register_payment(self, invoice, journal):
        wizard = self._create_payment_wizard(invoice)
        with Form(wizard) as form:
            form.journal_id = journal
        return wizard._create_payments()

    def _accounting_snapshot(self):
        domain = [("company_id", "=", self.env.company.id)]
        return {
            "moves": self.env["account.move"]
            .search(domain, order="id")
            .read(["state"], load=None),
            "lines": self.env["account.move.line"]
            .search(domain, order="id")
            .read(
                [
                    "move_id",
                    "account_id",
                    "partner_id",
                    "currency_id",
                    "debit",
                    "credit",
                    "amount_currency",
                    "amount_residual",
                    "amount_residual_currency",
                    "matched_debit_ids",
                    "matched_credit_ids",
                    "full_reconcile_id",
                ],
                load=None,
            ),
        }

    def _check_accounting_reference(self, move_type):
        invoice = self._create_move(self.product_a, 2000, move_type=move_type)
        gross = invoice.amount_total
        inbound = move_type == "out_invoice"
        journal = (
            self.inbound_withholding_journal if inbound else self.withholding_journal
        )
        amount = invoice.currency_id.round(gross * journal.withholding_tax_rate)
        fiscal_account = self.tax_receivable if inbound else self.tax_payable
        counterpart_type = "asset_receivable" if inbound else "liability_payable"
        invoice_counterpart = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == counterpart_type
        )
        withholding = self._register_payment(invoice, journal)

        self.assertEqual(withholding.move_id.state, "posted")
        self.assertEqual(withholding.payment_type, "inbound" if inbound else "outbound")
        self.assertEqual(withholding.outstanding_account_id, fiscal_account)
        self.assertEqual(len(withholding.move_id.line_ids), 2)
        fiscal_line = withholding.move_id.line_ids.filtered(
            lambda line: line.account_id == fiscal_account
        )
        counterpart = withholding.move_id.line_ids - fiscal_line
        self.assertRecordValues(
            fiscal_line,
            [
                {
                    "account_id": fiscal_account.id,
                    "partner_id": self.partner_a.id,
                    "debit": amount if inbound else 0,
                    "credit": 0 if inbound else amount,
                    "balance": amount if inbound else -amount,
                    "amount_residual": (
                        (amount if inbound else -amount)
                        if fiscal_account.reconcile
                        else 0
                    ),
                }
            ],
        )
        self.assertRecordValues(
            counterpart,
            [
                {
                    "account_id": invoice_counterpart.account_id.id,
                    "debit": 0 if inbound else amount,
                    "credit": amount if inbound else 0,
                    "amount_residual": 0,
                    "reconciled": True,
                }
            ],
        )
        self.assertTrue(withholding.is_reconciled)
        self.assertEqual(withholding.state, "in_process")
        self.assertAlmostEqual(invoice.amount_residual, gross - amount)
        self.assertEqual(invoice.amount_total, gross)
        self.assertFalse(
            withholding.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_cash"
            )
        )

        bank_payment = self._register_payment(invoice, self.bank_journal)

        self.assertAlmostEqual(bank_payment.amount, gross - amount)
        self.assertEqual(bank_payment.move_id.state, "posted")
        bank_line = bank_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.bank_journal.default_account_id
        )
        self.assertEqual(len(bank_line), 1)
        self.assertAlmostEqual(
            bank_line.balance, (gross - amount) * (1 if inbound else -1)
        )
        self.assertTrue(all(invoice_counterpart.mapped("reconciled")))
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(invoice.payment_state, "in_payment")
        before_confirmation = self._accounting_snapshot()

        withholding.action_validate_withholding()

        self.assertEqual(self._accounting_snapshot(), before_confirmation)
        self.assertEqual(withholding.state, "paid")
        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(invoice.amount_total, gross)
        self.assertEqual(invoice.amount_residual, 0)
        self.assertFalse(
            self.env["account.bank.statement.line"].search_count(
                [("journal_id", "=", journal.id)]
            )
        )

    def test_customer_withholding_posts_to_tax_receivable(self):
        self._check_accounting_reference("out_invoice")

    def test_supplier_withholding_posts_to_tax_payable(self):
        self._check_accounting_reference("in_invoice")

    def test_customer_withholding_with_native_tunisian_account_settings(self):
        self.tax_receivable.write(
            {
                "name": "Retenue à la source (434100)",
                "account_type": "liability_current",
                "reconcile": False,
            }
        )
        self._check_accounting_reference("out_invoice")
        self.assertFalse(self.tax_receivable.reconcile)

    def test_supplier_withholding_with_native_tunisian_account_settings(self):
        self.tax_payable.write(
            {"name": "État, retenues à la source (432000)", "reconcile": False}
        )
        self._check_accounting_reference("in_invoice")
        self.assertFalse(self.tax_payable.reconcile)

    def test_shared_journal_preserves_customer_and_supplier_accounting(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        self.inbound_withholding_rule.withholding_journal_id = journal
        self.inbound_withholding_journal = journal
        self._check_accounting_reference("out_invoice")
        self._check_accounting_reference("in_invoice")

    def test_refund_wizard_cannot_register_new_withholding(self):
        for move_type in ("out_refund", "in_refund"):
            with self.subTest(move_type=move_type):
                refund = self._create_move(self.product_a, 2000, move_type=move_type)
                wizard = self._create_payment_wizard(refund)
                self.assertNotIn(self.withholding_journal, wizard.available_journal_ids)
                wizard.journal_id = self.withholding_journal
                with self.assertRaises(UserError), self.cr.savepoint():
                    wizard._create_payments()
                self.assertFalse(refund.matched_payment_ids)
                self.assertEqual(refund.amount_residual, refund.amount_total)

    def test_standard_refunds_keep_bank_flow(self):
        for move_type, payment_type in (
            ("out_refund", "outbound"),
            ("in_refund", "inbound"),
        ):
            with self.subTest(move_type=move_type):
                refund = self._create_move(self.product_a, 2000, move_type=move_type)
                payment = self._register_payment(refund, self.bank_journal)

                self.assertEqual(payment.payment_type, payment_type)
                self.assertFalse(payment.is_withholding_tax_payment)
                self.assertEqual(
                    payment.outstanding_account_id, self.bank_journal.default_account_id
                )
                self.assertEqual(refund.amount_residual, 0)
                self.assertEqual(refund.payment_state, "paid")
                self.assertFalse(
                    payment.move_id.line_ids.filtered(
                        lambda line: (
                            line.account_id in (self.tax_receivable | self.tax_payable)
                        )
                    )
                )
