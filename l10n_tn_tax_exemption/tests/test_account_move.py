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

    def test_expired_exemption_reminder_uses_invoice_date(self):
        invoice = self._create_invoice(invoice_date="2025-01-01")
        self.assertEqual(invoice.company_id.l10n_tn_tax_exemption_reminder_months, 12)
        self.assertIn(
            self.exemption.name, invoice.l10n_tn_tax_exemption_reminder_warning
        )
        for invoice_date, expected in (
            ("2025-12-31", True),
            ("2026-01-01", False),
            ("2024-12-31", False),
        ):
            with self.subTest(invoice_date=invoice_date):
                invoice.invoice_date = invoice_date
                self.assertEqual(
                    bool(invoice.l10n_tn_tax_exemption_reminder_warning), expected
                )

    def test_expired_exemption_reminder_tracks_partner(self):
        self.partner_b.country_id = self.env.ref("base.tn")
        contact = self.env["res.partner"].create(
            {
                "name": "Invoice contact",
                "parent_id": self.partner_a.id,
                "country_id": self.partner_a.country_id.id,
            }
        )
        invoice = self._create_invoice(partner_id=contact.id, invoice_date="2025-01-01")
        self.assertTrue(invoice.l10n_tn_tax_exemption_reminder_warning)
        invoice.partner_id = self.partner_b
        self.assertFalse(invoice.l10n_tn_tax_exemption_reminder_warning)

    def test_expired_exemption_reminder_is_company_specific(self):
        company = self.env["res.company"].create(
            {"name": "Other reminder company", "country_id": self.env.ref("base.tn").id}
        )
        self.assertEqual(company.l10n_tn_tax_exemption_reminder_months, 12)
        self.env["res.config.settings"].create(
            {"company_id": company.id, "l10n_tn_tax_exemption_reminder_months": 3}
        )
        self.assertEqual(company.l10n_tn_tax_exemption_reminder_months, 3)
        invoice = self._create_invoice(invoice_date="2025-07-01")
        self.assertTrue(
            invoice.with_company(company).l10n_tn_tax_exemption_reminder_warning
        )
        invoice.company_id.l10n_tn_tax_exemption_reminder_months = 6
        self.assertFalse(invoice.l10n_tn_tax_exemption_reminder_warning)
        invoice.company_id.l10n_tn_tax_exemption_reminder_months = 0
        invoice.invoice_date = "2025-01-01"
        self.assertFalse(invoice.l10n_tn_tax_exemption_reminder_warning)

    def test_expired_exemption_reminder_only_on_draft_customer_documents(self):
        for move_type in ("out_invoice", "out_refund", "in_invoice", "out_receipt"):
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(
                    move_type=move_type, invoice_date="2025-01-01"
                )
                self.assertEqual(
                    bool(invoice.l10n_tn_tax_exemption_reminder_warning),
                    move_type in ("out_invoice", "out_refund"),
                )
                if invoice.is_sale_document():
                    invoice.action_post()
                    self.assertFalse(invoice.l10n_tn_tax_exemption_reminder_warning)

    def test_current_exemption_suppresses_expired_exemption_reminder(self):
        self.env["l10n_tn.tax_exemption"].create(
            {
                "name": "Renewed certificate",
                "partner_id": self.partner_a.id,
                "date_start": "2025-01-01",
                "date_end": "2025-12-31",
                "fiscal_position_id": self.exemption_position.id,
            }
        )
        invoice = self._create_invoice(invoice_date="2025-01-01")
        self.assertTrue(invoice.l10n_tn_tax_exemption_id)
        self.assertFalse(invoice.l10n_tn_tax_exemption_reminder_warning)

    def test_manually_selected_expired_exemption_still_has_reminder(self):
        invoice = self._create_invoice(
            invoice_date="2025-01-01", l10n_tn_tax_exemption_id=self.exemption.id
        )
        self.assertTrue(invoice.l10n_tn_tax_exemption_reminder_warning)

    def test_customer_credit_note_uses_exemption(self):
        credit_note = self._create_invoice(move_type="out_refund")
        self.assertEqual(credit_note.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(credit_note.fiscal_position_id, self.exemption_position)
        self.assertIn(self.exemption.name, credit_note.l10n_tn_tax_exemption_warning)
        self.assertTrue(credit_note.l10n_tn_tax_exemption_missing_warning)

    def test_other_document_types_skip_exemption(self):
        for move_type in ("in_invoice", "in_refund", "in_receipt", "out_receipt"):
            with self.subTest(move_type=move_type):
                move = self._create_invoice(move_type=move_type)
                self.assertFalse(move.l10n_tn_tax_exemption_id)
                self.assertFalse(move.l10n_tn_tax_exemption_warning)
                self.assertFalse(move.l10n_tn_tax_exemption_missing_warning)
                with self.assertRaises(ValidationError), self.env.cr.savepoint():
                    move.l10n_tn_tax_exemption_id = self.exemption

    def test_journal_entry_skips_exemption(self):
        move = self.env["account.move"].create(
            {"partner_id": self.partner_a.id, "date": "2024-01-01"}
        )
        self.assertFalse(move.l10n_tn_tax_exemption_id)
        self.assertFalse(move.l10n_tn_tax_exemption_warning)
        self.assertFalse(move.l10n_tn_tax_exemption_missing_warning)

    def test_exemption_warnings_track_missing_information(self):
        invoice = self._create_invoice()
        self.assertIn(self.exemption.name, invoice.l10n_tn_tax_exemption_warning)
        self.assertTrue(invoice.l10n_tn_tax_exemption_missing_warning)

        self.assertNotIn(
            "• Endorsed Purchase Order", invoice.l10n_tn_tax_exemption_warning
        )
        invoice.l10n_tn_endorsed_purchase_order = "BC-2024-001"
        self.assertNotIn(
            "• Endorsed Purchase Order", invoice.l10n_tn_tax_exemption_warning
        )

        self.exemption.date_issue = "2024-01-01"
        invoice.write(
            {
                "l10n_tn_endorsed_purchase_order": "BC-2024-001",
                "l10n_tn_endorsed_purchase_order_date": "2024-01-02",
                "l10n_tn_endorsed_purchase_order_file": b"dGVzdA==",
            }
        )
        self.assertFalse(invoice.l10n_tn_tax_exemption_missing_warning)
        self.assertIn("BC-2024-001", invoice.l10n_tn_tax_exemption_warning)

        invoice.l10n_tn_endorsed_purchase_order_file = False
        self.assertTrue(invoice.l10n_tn_tax_exemption_missing_warning)
        invoice.action_post()
        self.assertFalse(invoice.l10n_tn_tax_exemption_missing_warning)
        # the legal message stays available for the posted invoice report
        self.assertIn("BC-2024-001", invoice.l10n_tn_tax_exemption_warning)

    def test_invoice_without_exemption_has_no_warnings(self):
        invoice = self._create_invoice(l10n_tn_tax_exemption_id=False)
        self.assertFalse(invoice.l10n_tn_tax_exemption_warning)
        self.assertFalse(invoice.l10n_tn_tax_exemption_missing_warning)

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
