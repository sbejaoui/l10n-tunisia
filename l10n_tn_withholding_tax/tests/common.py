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


class WithholdingTaxTestCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_tunisian_parties(cls)
        cls.withholding_journal = cls.env["account.journal"].create(
            {
                "name": "Test RS 1.5%",
                "type": "bank",
                "code": "TRS15",
                "is_withholding_tax_journal": True,
                "withholding_tax_rate": 0.015,
            }
        )
        cls.other_withholding_journal = cls.env["account.journal"].create(
            {
                "name": "Test RS 5%",
                "type": "bank",
                "code": "TRS5",
                "is_withholding_tax_journal": True,
                "withholding_tax_rate": 0.05,
            }
        )
        cls.unruled_product = cls.product_a.copy(
            {"name": "Product without withholding rule"}
        )
        cls.withholding_rule = cls.env["l10n.tn.withholding.rule"].create(
            {
                "product_id": [Command.set(cls.product_a.ids)],
                "description": "Test withholding rule",
                "amount": 0,
                "withholding_journal_id": cls.withholding_journal.id,
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
