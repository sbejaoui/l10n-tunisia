from odoo import Command
from odoo.tests.common import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestAccountMove(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("tn")
    def setUpClass(cls):
        super().setUpClass()
        tn = cls.env.ref("base.tn")
        cls.partner_a.country_id = tn
        cls.stamp_tax_sale = cls._create_stamp_tax("sale")
        cls.stamp_tax_purchase = cls._create_stamp_tax("purchase")

    @classmethod
    def _create_stamp_tax(cls, type_tax_use):
        return cls.env["account.tax"].create({
            "name": f"Stamp Tax {type_tax_use}",
            "amount_type": "fixed",
            "amount": 1.0,
            "type_tax_use": type_tax_use,
            "l10n_tn_is_stamp_tax": True,
            "company_id": cls.company_data["company"].id,
            "country_id": cls.company_data["company"].account_fiscal_country_id.id,
        })

    def _create_invoice(self, move_type="out_invoice", partner=None):
        return self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": (partner or self.partner_a).id,
            "invoice_date": "2024-01-01",
            "invoice_line_ids": [Command.create({
                "product_id": self.product_a.id,
                "quantity": 1,
                "price_unit": 100,
            })],
        })

    def test_stamp_tax_addition(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.assertTrue(invoice._is_stamp_tax_exist())

    def test_sale_invoice_has_one_stamp_tax_line(self):
        invoice = self._create_invoice()
        invoice.action_post()

        stamp_lines = invoice.invoice_line_ids.filtered(
            "l10n_tn_is_stamp_tax"
        )

        self.assertEqual(len(stamp_lines), 1)
        self.assertEqual(stamp_lines.quantity, 1.0)
        self.assertEqual(stamp_lines.price_unit, 0.0)
        self.assertEqual(stamp_lines.tax_ids, self.stamp_tax_sale)

    def test_no_stamp_tax_for_foreign_partner(self):
        foreign_partner = self.env["res.partner"].create({
            "name": "Foreign Client",
            "country_id": self.env.ref("base.fr").id,
        })
        invoice = self._create_invoice(partner=foreign_partner)
        invoice.action_post()

        self.assertFalse(invoice._is_stamp_tax_exist())

    def test_purchase_invoice_uses_purchase_stamp_tax(self):
        bill = self._create_invoice(move_type="in_invoice")
        bill.action_post()

        stamp_lines = bill.invoice_line_ids.filtered(
            "l10n_tn_is_stamp_tax"
        )

        self.assertEqual(len(stamp_lines), 1)
        self.assertEqual(stamp_lines.tax_ids, self.stamp_tax_purchase)

    def test_batch_post_invoices_adds_stamp_tax(self):
        invoices = self._create_invoice() | self._create_invoice()
        invoices.action_post()

        for invoice in invoices:
            self.assertTrue(invoice._is_stamp_tax_exist())
