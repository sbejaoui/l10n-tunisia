# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestTaxExemptionCountry(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("tn")
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.country_id = cls.env.ref("base.tn")
        # support posting when stamp tax is installed alongside exemption
        if "l10n_tn_is_stamp_tax" in cls.env["account.tax"]._fields:
            cls.env["account.tax"].create(
                {
                    "name": "Neutral sales stamp tax",
                    "amount_type": "fixed",
                    "amount": 0,
                    "type_tax_use": "sale",
                    "company_id": cls.env.company.id,
                    "l10n_tn_is_stamp_tax": True,
                }
            )
        cls.exemption_position = cls.env["account.fiscal.position"].create(
            {"name": "Tunisian exemption", "company_id": cls.env.company.id}
        )
        cls.exemption_tax = cls.tax_sale_a.copy(
            {
                "name": "Exemption test tax",
                "amount": 0,
                "original_tax_ids": [Command.set(cls.tax_sale_a.ids)],
                "fiscal_position_ids": [Command.set(cls.exemption_position.ids)],
            }
        )
        cls.product_a.taxes_id = cls.tax_sale_a
        cls.exemption = cls.env["l10n_tn.tax_exemption"].create(
            {
                "name": "TN certificate",
                "partner_id": cls.partner_a.id,
                "date_start": "2024-01-01",
                "date_end": "2024-12-31",
                "fiscal_position_id": cls.exemption_position.id,
            }
        )

    def _create_invoice(self, **values):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-01",
                "invoice_line_ids": [
                    Command.create({"product_id": self.product_a.id, "price_unit": 100})
                ],
                **values,
            }
        )

    def test_domestic_invoice_uses_exemption(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)

    def test_fiscal_position_change_updates_existing_line_taxes(self):
        invoice = self._create_invoice(
            l10n_tn_tax_exemption_id=False, fiscal_position_id=False
        )
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax_sale_a)

        with Form(invoice) as form:
            form.fiscal_position_id = self.exemption_position
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.exemption_tax)
        self.assertEqual(invoice.amount_tax, 0)

        with Form(invoice) as form:
            form.fiscal_position_id = self.env["account.fiscal.position"]
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax_sale_a)
        self.assertGreater(invoice.amount_tax, 0)

    def test_partner_change_restores_and_reapplies_line_taxes(self):
        self.partner_b.country_id = self.env.ref("base.tn")
        self.partner_b.property_account_position_id = False
        invoice = self._create_invoice()
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.exemption_tax)

        with Form(invoice) as form:
            form.partner_id = self.partner_b
        self.assertFalse(invoice.l10n_tn_tax_exemption_id)
        self.assertFalse(invoice.fiscal_position_id)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax_sale_a)

        with Form(invoice) as form:
            form.partner_id = self.partner_a
        self.assertEqual(invoice.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.exemption_tax)

    def test_foreign_or_missing_partner_country_skips_exemption(self):
        for country in (self.env.ref("base.fr"), False):
            with self.subTest(country=country):
                self.partner_a.country_id = country
                invoice = self._create_invoice()
                self.assertFalse(invoice.l10n_tn_tax_exemption_id)
                self.assertNotEqual(invoice.fiscal_position_id, self.exemption_position)

    def test_foreign_company_skips_exemption(self):
        self.company_data["company"].country_id = self.env.ref("base.fr")
        self.assertFalse(self._create_invoice().l10n_tn_tax_exemption_id)

    def test_draft_country_change_removes_exemption_and_fiscal_position(self):
        invoice = self._create_invoice()
        self.partner_a.country_id = self.env.ref("base.fr")
        self.assertFalse(invoice.l10n_tn_tax_exemption_id)
        self.assertNotEqual(invoice.fiscal_position_id, self.exemption_position)

    def test_posted_document_keeps_its_exemption_when_country_changes(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.partner_a.country_id = self.env.ref("base.fr")
        self.assertEqual(invoice.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)

        invoice.button_draft()
        self.assertFalse(invoice.l10n_tn_tax_exemption_id)
        self.assertNotEqual(invoice.fiscal_position_id, self.exemption_position)

    def test_manual_foreign_exemption_is_rejected(self):
        self.partner_a.country_id = self.env.ref("base.fr")
        with self.assertRaises(ValidationError):
            self._create_invoice(l10n_tn_tax_exemption_id=self.exemption.id)
        invoice = self._create_invoice()
        with self.assertRaises(ValidationError):
            invoice.l10n_tn_tax_exemption_id = self.exemption
