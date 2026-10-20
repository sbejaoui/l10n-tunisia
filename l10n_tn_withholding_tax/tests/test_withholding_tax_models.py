# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged
from odoo.tools.misc import formatLang

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingTaxModels(WithholdingTaxTestCommon):
    # Purpose: a journal must retain its withholding flag and rate.
    def test_withholding_journal_configuration(self):
        self.assertTrue(self.withholding_journal.is_withholding_tax_journal)
        self.assertEqual(self.withholding_journal.withholding_tax_rate, 0.015)
        self.assertFalse(
            self.company_data["default_journal_bank"].is_withholding_tax_journal
        )

    # Purpose: a negative minimum amount must be rejected when a rule is saved.
    def test_rule_rejects_negative_minimum_amount(self):
        with self.assertRaises(ValidationError):
            self.withholding_rule.amount = -1

    # Purpose: a rule applies when its product is present and its threshold is met.
    def test_rule_matches_product_and_minimum_amount(self):
        matching_bill = self._create_move(self.product_a, 2000)
        unruled_bill = self._create_move(self.unruled_product, 2000)

        self.withholding_rule.amount = matching_bill.amount_total + 1
        self.assertNotIn(
            self.withholding_rule,
            self.withholding_rule._get_applicable_rules(matching_bill),
        )

        self.withholding_rule.amount = matching_bill.amount_total
        self.assertIn(
            self.withholding_rule,
            self.withholding_rule._get_applicable_rules(matching_bill),
        )
        self.assertFalse(self.withholding_rule._get_applicable_rules(unruled_bill))

    # Purpose: withholding, net amount, and alert text use the full bill total.
    def test_rule_calculates_amount_net_amount_and_alert_message(self):
        bill = self._create_move(self.product_a, 2000)
        amount = self.withholding_rule._get_withholding_amount(bill)
        net_amount = self.withholding_rule._get_net_amount(bill)
        message = self.withholding_rule._get_withholding_alert_message(
            amount, bill.currency_id, bill
        )

        self.assertAlmostEqual(
            amount,
            bill.amount_total * self.withholding_journal.withholding_tax_rate,
        )
        self.assertAlmostEqual(net_amount, bill.amount_total - amount)
        self.assertIn(self.product_a.display_name, message)
        self.assertIn(self.withholding_journal.name, message)
        self.assertIn(
            formatLang(self.env, amount, currency_obj=bill.currency_id), message
        )

    # Purpose: RS eligibility is false below 1,000 and true from 1,000.
    def test_move_computes_rs_eligibility_from_total(self):
        below_threshold_bill = self._create_move(self.product_a, 800)
        at_threshold_bill = self._create_move(self.product_a, 1000)

        self.assertFalse(below_threshold_bill.is_rs_eligible)
        self.assertTrue(at_threshold_bill.is_rs_eligible)
