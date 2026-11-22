# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import new_test_user, tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestPaymentAllocation(WithholdingTaxTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["l10n.tn.withholding.rule"].create(
            [
                {
                    "product_id": [Command.set(cls.product_b.ids)],
                    "description": "Second invoice withholding",
                    "move_type": move_type,
                    "withholding_journal_id": journal.id,
                }
                for move_type, journal in (
                    ("out_invoice", cls.other_inbound_withholding_journal),
                    ("in_invoice", cls.other_withholding_journal),
                )
            ]
        )

    def _allocation_wizard(self, handling="keep_unpaid", move_type="out_invoice"):
        invoices = self._create_move(self.product_a, 1000, move_type=move_type)
        invoices |= self._create_move(self.product_b, 2000, move_type=move_type)
        wizard = self._create_payment_wizard(invoices)
        with Form(wizard) as form:
            form.journal_id = self.company_data["default_journal_bank"]
            form.withholding_tax_applicable = True
            form.withholding_handling = handling
        return wizard, invoices

    def test_withholding_option_requires_multiple_eligible_invoices(self):
        invoices = self._create_move(self.product_a, 1000, move_type="out_invoice")
        self.assertFalse(
            self._create_payment_wizard(invoices).show_withholding_tax_applicable
        )
        invoices |= self._create_move(self.product_b, 2000, move_type="out_invoice")
        self.assertTrue(
            self._create_payment_wizard(invoices).show_withholding_tax_applicable
        )

        self.partner_a.country_id = self.env.ref("base.us")
        self.assertFalse(
            self._create_payment_wizard(invoices).show_withholding_tax_applicable
        )
        self.partner_a.country_id = self.env.ref("base.tn")
        self.company_data["company"].country_id = self.env.ref("base.fr")
        self.assertFalse(
            self._create_payment_wizard(invoices).show_withholding_tax_applicable
        )

    def test_withholding_option_is_hidden_without_matching_document_rules(self):
        journals = (
            self.inbound_withholding_journal | self.other_inbound_withholding_journal
        )
        rules = self.env["l10n.tn.withholding.rule"].search(
            [("withholding_journal_id", "in", journals.ids)]
        )
        rules.move_type = "in_invoice"
        invoices = self._create_move(self.product_a, 1000, move_type="out_invoice")
        invoices |= self._create_move(self.product_b, 2000, move_type="out_invoice")
        self.assertFalse(
            self._create_payment_wizard(invoices).show_withholding_tax_applicable
        )

    def test_one_receipt_leaves_withholding_on_each_invoice(self):
        wizard, invoices = self._allocation_wizard()
        expected = {
            line.invoice_id.id: line.withholding_amount
            for line in wizard.withholding_allocation_line_ids
        }
        payment = wizard._create_payments()

        self.assertEqual(len(payment), 1)
        self.assertFalse(payment.is_withholding_tax_payment)
        self.assertTrue(payment.is_reconciled)
        self.assertCountEqual(payment.invoice_ids.ids, invoices.ids)
        for invoice in invoices:
            self.assertAlmostEqual(invoice.amount_residual, expected[invoice.id])
            self.assertEqual(invoice.payment_state, "partial")
            self.assertFalse(
                invoice.matched_payment_ids.filtered("is_withholding_tax_payment")
            )

    def test_pay_creates_individual_withholding_and_one_receipt(self):
        wizard, invoices = self._allocation_wizard(handling="pay")
        payment = wizard._create_payments()
        self.assertEqual(len(payment), 1)
        withholding = invoices.matched_payment_ids.filtered(
            "is_withholding_tax_payment"
        )
        self.assertEqual(len(withholding), 2)
        self.assertCountEqual(
            withholding.journal_id.ids,
            (
                self.inbound_withholding_journal
                | self.other_inbound_withholding_journal
            ).ids,
        )
        for invoice in invoices:
            self.assertEqual(invoice.amount_residual, 0)
            self.assertEqual(invoice.payment_state, "in_payment")
        self.assertEqual(withholding.mapped("state"), ["in_process", "in_process"])
        self.assertFalse(any(withholding.mapped("is_matched")))

    def test_partial_cash_is_allocated_as_edited(self):
        wizard, invoices = self._allocation_wizard()
        expected = {}
        for line in wizard.withholding_allocation_line_ids:
            line.cash_amount = line.currency_id.round(line.cash_amount / 2)
            expected[line.invoice_id.id] = line.invoice_balance - line.cash_amount
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )
        self.assertTrue(wizard.withholding_allocation_warning)

        payment = wizard._create_payments()

        self.assertEqual(len(payment), 1)
        self.assertTrue(payment.is_reconciled)
        for invoice in invoices:
            self.assertAlmostEqual(invoice.amount_residual, expected[invoice.id])

    def test_partial_cash_and_registered_withholding(self):
        wizard, invoices = self._allocation_wizard(handling="pay")
        expected = {}
        for line in wizard.withholding_allocation_line_ids:
            line.cash_amount = line.currency_id.round(line.cash_amount / 2)
            expected[line.invoice_id.id] = (
                line.invoice_balance - line.cash_amount - line.withholding_amount
            )
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )
        payment = wizard._create_payments()
        self.assertEqual(len(payment), 1)
        for invoice in invoices:
            self.assertAlmostEqual(invoice.amount_residual, expected[invoice.id])
            self.assertEqual(
                len(invoice.matched_payment_ids.filtered("is_withholding_tax_payment")),
                1,
            )

    def test_foreign_currency_and_mixed_partners_are_rejected(self):
        wizard, _invoices = self._allocation_wizard()
        foreign_currency = (
            self.env.ref("base.EUR")
            if wizard.company_currency_id != self.env.ref("base.EUR")
            else self.env.ref("base.USD")
        )
        wizard.currency_id = foreign_currency
        with self.assertRaises(UserError):
            wizard._create_payments()

        invoice = self._create_move(self.product_a, 1000, move_type="out_invoice")
        other_invoice = invoice.copy({"partner_id": self.partner_b.id})
        other_invoice.action_post()
        mixed = self._create_payment_wizard(invoice | other_invoice)
        mixed.withholding_tax_applicable = True
        mixed.amount = sum(mixed.withholding_allocation_line_ids.mapped("cash_amount"))
        with self.assertRaises(UserError):
            mixed._create_payments()

    def test_amount_mismatch_is_blocked_before_creating_payment(self):
        wizard, invoices = self._allocation_wizard()
        wizard.amount += 1
        self.assertTrue(wizard.withholding_allocation_warning)
        with self.assertRaises(UserError):
            wizard._create_payments()
        self.assertFalse(invoices.matched_payment_ids)

    def test_incompatible_journal_is_blocked(self):
        wizard, _invoices = self._allocation_wizard()
        line = wizard.withholding_allocation_line_ids[0]
        line.withholding_journal_ids = self.env["account.journal"].browse(
            self.company_data["default_journal_bank"].id
        )
        with self.assertRaises(UserError):
            wizard._create_payments()

    def test_excess_allocation_is_blocked(self):
        wizard, _invoices = self._allocation_wizard()
        line = wizard.withholding_allocation_line_ids[0]
        line.cash_amount = line.invoice_balance
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )
        with self.assertRaises(UserError):
            wizard._create_payments()

    def test_removing_withholding_from_one_invoice(self):
        wizard, _invoices = self._allocation_wizard()
        line = wizard.withholding_allocation_line_ids[0]
        line.withholding_journal_ids = [Command.clear()]
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )

        payment = wizard._create_payments()

        self.assertEqual(len(payment), 1)
        self.assertEqual(line.invoice_id.amount_residual, 0)

    def test_cash_journal_still_creates_one_payment(self):
        wizard, _invoices = self._allocation_wizard()
        expected_amount = wizard.amount
        wizard.journal_id = self.env["account.journal"].create(
            {"name": "Allocation Cash", "code": "ALCS", "type": "cash"}
        )
        self.assertEqual(wizard.amount, expected_amount)
        payment = wizard._create_payments()
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment.amount, expected_amount)
        self.assertTrue(payment.is_reconciled)

    def test_journal_switch_keeps_edited_allocations_and_receipt_amount(self):
        wizard, invoices = self._allocation_wizard()
        for line in wizard.withholding_allocation_line_ids:
            line.cash_amount = line.currency_id.round(line.cash_amount / 2)
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )
        expected_amount = wizard.amount
        expected_residuals = {
            line.invoice_id.id: line.invoice_balance - line.cash_amount
            for line in wizard.withholding_allocation_line_ids
        }
        wizard.journal_id = self.env["account.journal"].create(
            {"name": "Other Allocation Bank", "code": "ALBK", "type": "bank"}
        )

        self.assertEqual(wizard.amount, expected_amount)
        payment = wizard._create_payments()

        self.assertEqual(payment.amount, expected_amount)
        for invoice in invoices:
            self.assertAlmostEqual(
                invoice.amount_residual, expected_residuals[invoice.id]
            )

    def test_editing_bank_amount_fills_invoice_net_balances_in_order(self):
        wizard, invoices = self._allocation_wizard()
        lines = wizard.withholding_allocation_line_ids
        net_amounts = {
            line.invoice_id.id: line.invoice_balance - line.withholding_amount
            for line in lines
        }
        withholding_amounts = {
            line.invoice_id.id: line.withholding_amount for line in lines
        }
        first_net = net_amounts[lines[0].invoice_id.id]
        partial_second = wizard.currency_id.round(
            net_amounts[lines[1].invoice_id.id] / 2
        )
        amount = first_net + partial_second
        with Form(wizard) as form:
            form.amount = amount

        self.assertAlmostEqual(wizard.amount, amount)
        self.assertAlmostEqual(sum(lines.mapped("cash_amount")), amount)
        self.assertAlmostEqual(lines[0].cash_amount, first_net)
        self.assertAlmostEqual(lines[1].cash_amount, partial_second)
        for line in lines:
            self.assertEqual(
                line.withholding_amount, withholding_amounts[line.invoice_id.id]
            )
        expected_residuals = {
            line.invoice_id.id: line.invoice_balance - line.cash_amount
            for line in lines
        }
        payment = wizard._create_payments()
        self.assertEqual(len(payment), 1)
        self.assertAlmostEqual(payment.amount, amount)
        self.assertAlmostEqual(
            lines[0].invoice_id.amount_residual, lines[0].withholding_amount
        )
        for invoice in invoices:
            self.assertAlmostEqual(
                invoice.amount_residual, expected_residuals[invoice.id]
            )

    def test_amount_distribution_handles_currency_rounding(self):
        wizard, _invoices = self._allocation_wizard()
        amount = wizard.currency_id.rounding
        with Form(wizard) as form:
            form.amount = amount

        self.assertAlmostEqual(
            sum(wizard.withholding_allocation_line_ids.mapped("cash_amount")), amount
        )
        self.assertEqual(wizard.withholding_allocation_line_ids[0].cash_amount, amount)
        self.assertEqual(wizard.withholding_allocation_line_ids[1].cash_amount, 0)
        for line in wizard.withholding_allocation_line_ids:
            self.assertGreaterEqual(line.cash_amount, 0)
            self.assertLessEqual(
                line.cash_amount, line.invoice_balance - line.withholding_amount
            )

    def test_editing_table_preserves_manual_distribution(self):
        wizard, _invoices = self._allocation_wizard()
        lines = wizard.withholding_allocation_line_ids
        unchanged_amount = lines[1].cash_amount
        with Form(wizard) as form:
            with form.withholding_allocation_line_ids.edit(0) as allocation:
                allocation.cash_amount = 10

        self.assertEqual(lines[0].cash_amount, 10)
        self.assertEqual(lines[1].cash_amount, unchanged_amount)
        self.assertEqual(wizard.amount, 10 + unchanged_amount)

    def test_excess_bank_amount_keeps_warning_without_using_withholding(self):
        wizard, _invoices = self._allocation_wizard()
        original_allocations = wizard.withholding_allocation_line_ids.mapped(
            "cash_amount"
        )
        excessive_amount = wizard.amount + 10
        with Form(wizard) as form:
            form.amount = excessive_amount

        self.assertEqual(wizard.amount, excessive_amount)
        self.assertEqual(
            wizard.withholding_allocation_line_ids.mapped("cash_amount"),
            original_allocations,
        )
        self.assertTrue(wizard.withholding_allocation_warning)
        with self.assertRaises(UserError):
            wizard._create_payments()

    def test_multiple_taxes_on_one_invoice(self):
        wizard, invoices = self._allocation_wizard(handling="pay")
        line = wizard.withholding_allocation_line_ids.filtered(
            lambda allocation: allocation.invoice_id == invoices[0]
        )
        self.env["l10n.tn.withholding.rule"].create(
            {
                "withholding_journal_id": self.other_inbound_withholding_journal.id,
                "move_type": "out_invoice",
                "amount": 0,
            }
        )
        line.withholding_journal_ids |= self.other_inbound_withholding_journal
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )
        payment = wizard._create_payments()
        self.assertEqual(len(payment), 1)
        self.assertEqual(
            len(invoices[0].matched_payment_ids.filtered("is_withholding_tax_payment")),
            2,
        )
        self.assertEqual(invoices[0].amount_residual, 0)

    def test_stale_balance_is_blocked(self):
        wizard, invoices = self._allocation_wizard()
        other_wizard = self._create_payment_wizard(invoices[0])
        other_wizard.journal_id = self.company_data["default_journal_bank"]
        other_wizard.amount = 10
        other_wizard._create_payments()
        with self.assertRaises(UserError):
            wizard._create_payments()

    def test_toggle_sets_one_payment_and_net_amount(self):
        invoices = self._create_move(self.product_a, 1000, move_type="out_invoice")
        invoices |= self._create_move(self.product_b, 2000, move_type="out_invoice")
        wizard = self._create_payment_wizard(invoices)
        with Form(wizard) as form:
            form.withholding_tax_applicable = True
            self.assertFalse(form.withholding_allocation_warning)
        allocations = wizard.withholding_allocation_line_ids
        self.assertCountEqual(allocations.invoice_id.ids, invoices.ids)
        for line in allocations:
            self.assertEqual(line.invoice_balance, line.invoice_id.amount_residual)
            self.assertTrue(line.withholding_journal_ids)
            self.assertGreater(line.withholding_amount, 0)
        self.assertTrue(wizard.group_payment)
        self.assertAlmostEqual(
            wizard.amount,
            sum(wizard.withholding_allocation_line_ids.mapped("cash_amount")),
        )

    def test_partial_payment_warning_does_not_reject_virtual_journals(self):
        wizard, _invoices = self._allocation_wizard()
        with Form(wizard) as form:
            form.amount = 100
            self.assertTrue(form.withholding_allocation_warning)
            self.assertIn("partial payment", form.withholding_allocation_warning)
            self.assertNotIn(
                "do not match its applicable rules", form.withholding_allocation_warning
            )

    def test_vendor_payment_uses_same_allocation(self):
        wizard, invoices = self._allocation_wizard(move_type="in_invoice")
        expected = {
            line.invoice_id.id: line.withholding_amount
            for line in wizard.withholding_allocation_line_ids
        }
        payment = wizard._create_payments()
        self.assertEqual(payment.payment_type, "outbound")
        self.assertTrue(payment.is_reconciled)
        for invoice in invoices:
            self.assertAlmostEqual(invoice.amount_residual, expected[invoice.id])

    def test_vendor_pay_registers_withholding_and_net_bank_payment(self):
        wizard, invoices = self._allocation_wizard(
            handling="pay", move_type="in_invoice"
        )
        expected = {
            line.invoice_id.id: (line.withholding_amount, line.cash_amount)
            for line in wizard.withholding_allocation_line_ids
        }
        payment = wizard._create_payments()
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment.payment_type, "outbound")
        self.assertFalse(payment.is_withholding_tax_payment)
        self.assertEqual(payment.move_id.state, "posted")
        self.assertAlmostEqual(
            payment.amount, sum(net for _tax, net in expected.values())
        )
        liquidity, counterpart, _writeoff = payment._seek_for_lines()
        self.assertAlmostEqual(sum(liquidity.mapped("balance")), -payment.amount)
        self.assertFalse(
            liquidity.filtered(lambda line: line.account_id == self.tax_payable)
        )
        self.assertTrue(all(counterpart.mapped("reconciled")))
        withholding = invoices.matched_payment_ids.filtered(
            "is_withholding_tax_payment"
        )
        self.assertEqual(len(withholding), 2)
        self.assertCountEqual(
            withholding.journal_id.ids,
            (self.withholding_journal | self.other_withholding_journal).ids,
        )
        for invoice in invoices:
            with self.subTest(invoice=invoice.name):
                tax, net = expected[invoice.id]
                fiscal_payment = invoice.matched_payment_ids & withholding
                self.assertEqual(len(fiscal_payment), 1)
                self.assertEqual(fiscal_payment.payment_type, "outbound")
                self.assertAlmostEqual(fiscal_payment.amount, tax)
                self.assertEqual(fiscal_payment.move_id.state, "posted")
                self.assertEqual(fiscal_payment.state, "in_process")
                fiscal, supplier, _writeoff = fiscal_payment._seek_for_lines()
                self.assertEqual(fiscal.account_id, self.tax_payable)
                self.assertAlmostEqual(fiscal.credit, tax)
                self.assertEqual(fiscal.debit, 0)
                self.assertEqual(
                    supplier.account_id, invoice.partner_id.property_account_payable_id
                )
                self.assertAlmostEqual(supplier.debit, tax)
                self.assertEqual(supplier.credit, 0)
                self.assertTrue(supplier.reconciled)
                self.assertAlmostEqual(invoice.amount_total, tax + net)
                self.assertEqual(invoice.amount_residual, 0)
                self.assertEqual(invoice.payment_state, "in_payment")

    def test_invoicing_user_can_allocate_without_managing_rules(self):
        user = new_test_user(
            self.env,
            login="withholding_allocation_user",
            groups="account.group_account_invoice",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        invoices = self._create_move(self.product_a, 1000, move_type="out_invoice")
        invoices |= self._create_move(self.product_b, 2000, move_type="out_invoice")
        wizard = (
            self.env["account.payment.register"]
            .with_user(user)
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create({"withholding_tax_applicable": True})
        )
        wizard.journal_id = self.company_data["default_journal_bank"]
        wizard.amount = sum(
            wizard.withholding_allocation_line_ids.mapped("cash_amount")
        )

        self.assertEqual(len(wizard._create_payments()), 1)
