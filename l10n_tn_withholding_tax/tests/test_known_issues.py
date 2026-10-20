# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest import skip

from odoo import Command
from odoo.tests import Form
from odoo.tests.common import tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestKnownWithholdingIssues(WithholdingTaxTestCommon):
    # Purpose: cancelling withholding must make the rule and journal available again.
    @skip("Known issue: cancelled withholding payments still count as paid.")
    def test_cancelled_withholding_payment_makes_rule_available_again(self):
        bill = self._create_move(self.product_a, 2000)
        wizard = self._create_payment_wizard(bill)

        with Form(wizard) as form:
            form.journal_id = self.withholding_journal

        payment = wizard._create_payments()
        payment.action_cancel()
        next_wizard = self._create_payment_wizard(bill)

        self.assertFalse(bill.is_rs_paid)
        self.assertIn(
            self.withholding_rule,
            self.withholding_rule._get_applicable_rules(bill),
        )
        self.assertIn(
            self.withholding_journal,
            next_wizard.available_journal_ids,
        )

    # Purpose: mixed-currency selections must be registered separately.
    @skip("Known issue: mixed-currency selections crash while computing the alert.")
    def test_mixed_currency_bills_hide_withholding_journals(self):
        usd = self.env.ref("base.USD")
        usd.active = True
        tnd_invoice = self._create_move(self.product_a, 2000, move_type="out_invoice")
        usd_invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-01",
                "currency_id": usd.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 1,
                            "price_unit": 2000,
                        }
                    )
                ],
            }
        )
        usd_invoice.action_post()
        wizard = self._create_payment_wizard(tnd_invoice | usd_invoice)

        with Form(wizard) as form:
            self.assertNotIn(self.withholding_journal, form.available_journal_ids)
            self.assertIn("separately", form.withholding_tax_alert)

    # Purpose: when one product has several rules, only the rule with the highest
    # applicable minimum amount must apply to the bill.
    @skip(
        "Known issue: rule lookup selects the first rule instead of the "
        "highest applicable threshold."
    )
    def test_product_uses_highest_applicable_rule_threshold(self):
        higher_threshold_rule = self.env["l10n.tn.withholding.rule"].create(
            {
                "product_id": [Command.set(self.product_a.ids)],
                "description": "RS 5% above 1,000 TND",
                "amount": 1000,
                "withholding_journal_id": self.other_withholding_journal.id,
            }
        )
        bill = self._create_move(self.product_a, 2000)

        applicable_rules = self.withholding_rule._get_applicable_rules(bill)

        self.assertEqual(applicable_rules, higher_threshold_rule)
