# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).

from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestDomesticTransaction(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("tn")
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.country_id = cls.env.ref("base.tn")

    def test_country_combinations(self):
        company = self.company_data["company"]
        tn = self.env.ref("base.tn")
        fr = self.env.ref("base.fr")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": company.id,
                "partner_id": self.partner_a.id,
            }
        )
        for company_country, partner_country, expected in (
            (tn, tn, True),
            (tn, fr, False),
            (fr, tn, False),
            (fr, fr, False),
            (tn, False, False),
            (False, tn, False),
        ):
            with self.subTest(company=company_country, partner=partner_country):
                company.country_id = company_country
                self.partner_a.country_id = partner_country
                self.assertEqual(move._l10n_tn_is_domestic_transaction(), expected)
                self.assertEqual(move.l10n_tn_is_domestic_transaction, expected)

    def test_uses_document_company_instead_of_active_company(self):
        foreign_company = self.env["res.company"].create(
            {"name": "Foreign Company", "country_id": self.env.ref("base.fr").id}
        )
        move = self.env["account.move"].new(
            {
                "company_id": self.company_data["company"].id,
                "partner_id": self.partner_a.id,
            }
        )
        self.assertTrue(
            move.with_company(foreign_company)._l10n_tn_is_domestic_transaction()
        )
        move.company_id = foreign_company
        self.assertFalse(move._l10n_tn_is_domestic_transaction())
