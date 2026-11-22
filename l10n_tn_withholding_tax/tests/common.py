# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


def setup_tunisian_parties(test_class):
    test_class.company_data["company"].country_id = test_class.env.ref("base.tn")
    test_class.partner_a.country_id = test_class.env.ref("base.tn")
    # keep withholding amounts independent of stamp tax when both addons are installed
    if "l10n_tn_is_stamp_tax" in test_class.env["account.tax"]._fields:
        test_class.env["account.tax"].create(
            [
                {
                    "name": f"Neutral stamp tax {tax_type}",
                    "amount_type": "fixed",
                    "amount": 0,
                    "type_tax_use": tax_type,
                    "company_id": test_class.company_data["company"].id,
                    "l10n_tn_is_stamp_tax": True,
                }
                for tax_type in ("sale", "purchase")
            ]
        )


def setup_withholding_accounts(test_class):
    test_class.tax_receivable, test_class.tax_payable = test_class.env[
        "account.account"
    ].create(
        [
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "reconcile": True,
                "company_ids": [Command.set(test_class.env.company.ids)],
            }
            for name, code, account_type in (
                ("Withholding tax receivable", "991501", "asset_current"),
                ("Withholding tax payable", "991502", "liability_current"),
            )
        ]
    )


class WithholdingTaxTestCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_tunisian_parties(cls)
        setup_withholding_accounts(cls)
        cls.withholding_journal = cls.env["account.journal"].create(
            {
                "name": "Test RS 1.5%",
                "type": "bank",
                "code": "TRS15",
                "is_withholding_tax_journal": True,
                "withholding_direction": "outbound",
                "withholding_tax_rate": 0.015,
            }
        )
        cls.other_withholding_journal = cls.env["account.journal"].create(
            {
                "name": "Test RS 5%",
                "type": "bank",
                "code": "TRS5",
                "is_withholding_tax_journal": True,
                "withholding_direction": "outbound",
                "withholding_tax_rate": 0.05,
            }
        )
        cls.inbound_withholding_journal = cls.withholding_journal.copy(
            {
                "name": "Test Incoming RS 1.5%",
                "code": "TIR15",
                "withholding_direction": "inbound",
            }
        )
        cls.other_inbound_withholding_journal = cls.other_withholding_journal.copy(
            {
                "name": "Test Incoming RS 5%",
                "code": "TIR5",
                "withholding_direction": "inbound",
            }
        )
        for journal in cls.withholding_journal | cls.other_withholding_journal:
            journal.outbound_payment_method_line_ids.payment_account_id = (
                cls.tax_payable
            )
        for journal in (
            cls.inbound_withholding_journal | cls.other_inbound_withholding_journal
        ):
            journal.inbound_payment_method_line_ids.payment_account_id = (
                cls.tax_receivable
            )
        cls.unruled_product = cls.product_a.copy(
            {"name": "Product without withholding rule"}
        )
        cls.withholding_rule = cls.env["l10n.tn.withholding.rule"].create(
            {
                "product_id": [Command.set(cls.product_a.ids)],
                "description": "Test withholding rule",
                "amount": 0,
                "move_type": "in_invoice",
                "withholding_journal_id": cls.withholding_journal.id,
            }
        )
        cls.inbound_withholding_rule = cls.withholding_rule.copy(
            {
                "move_type": "out_invoice",
                "withholding_journal_id": cls.inbound_withholding_journal.id,
            }
        )

    def _create_move(self, product, price_unit, move_type="in_invoice"):
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": price_unit,
                        }
                    )
                ],
            }
        )
        move.action_post()
        return move

    def _create_payment_wizard(self, moves):
        return (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=moves.ids)
            .create({})
        )
