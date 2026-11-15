# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged
from odoo.tools.misc import formatLang

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingTaxModels(WithholdingTaxTestCommon):
    def test_rules_and_available_journals_are_scoped_to_invoice_company(self):
        company = self.company_data["company"]
        other_company = self.setup_other_company()["company"]
        other_journal = (
            self.env["account.journal"]
            .with_company(other_company)
            .create(
                {
                    "name": "Other company withholding",
                    "code": "OTHRS",
                    "type": "bank",
                    "company_id": other_company.id,
                    "is_withholding_tax_journal": True,
                    "withholding_tax_rate": 0.01,
                }
            )
        )
        self.env["l10n.tn.withholding.rule"].with_company(other_company).create(
            [
                {"withholding_journal_id": other_journal.id},
                {
                    "product_id": [Command.set(self.product_a.ids)],
                    "withholding_journal_id": other_journal.id,
                },
            ]
        )
        bill = self._create_move(self.product_a, 2000)
        unruled_bill = self._create_move(self.unruled_product, 2000)
        rules = self.env["l10n.tn.withholding.rule"].with_context(
            allowed_company_ids=company.ids
        )

        self.assertEqual(rules._get_applicable_rules(bill), self.withholding_rule)
        self.assertFalse(rules._get_applicable_rules(unruled_bill))
        wizard = self._create_payment_wizard(bill).with_context(
            allowed_company_ids=company.ids
        )
        self.assertIn(self.withholding_journal, wizard.available_journal_ids)
        self.assertNotIn(other_journal, wizard.available_journal_ids)

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

    def test_rule_without_products_matches_minimum_amount(self):
        bill = self._create_move(self.unruled_product, 2000)
        self.withholding_rule.product_id = [Command.clear()]

        for minimum, expected in (
            (bill.amount_total + 1, False),
            (bill.amount_total, True),
            (bill.amount_total - 1, True),
            (0, True),
        ):
            with self.subTest(minimum=minimum):
                self.withholding_rule.amount = minimum
                self.assertEqual(
                    self.withholding_rule
                    in self.withholding_rule._get_applicable_rules(bill),
                    expected,
                )

    def test_rule_without_products_matches_productless_invoice_line(self):
        bill = self._create_move(self.unruled_product, 2000)
        bill.button_draft()
        bill.invoice_line_ids.product_id = False
        bill.action_post()
        self.withholding_rule.product_id = [Command.clear()]
        self.withholding_rule.amount = bill.amount_total

        self.assertIn(
            self.withholding_rule,
            self.withholding_rule._get_applicable_rules(bill),
        )

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
