from odoo import Command
from odoo.tests.common import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestAccountMove(AccountTestInvoicingCommon):

    chart_template = 'tn_pcg'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tn = cls.env.ref("base.tn")
        cls.company_data['company'].country_id = tn
        cls.partner_a.country_id = tn
        cls.stamp_tax_sale = cls.env['account.chart.template'].ref("tax_stamp_sale")
        cls.stamp_tax_purchase = cls.env['account.chart.template'].ref("tax_stamp_purchase")

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
            lambda line: self.stamp_tax_sale in line.tax_ids
        )

        self.assertEqual(len(stamp_lines), 1)
        self.assertEqual(stamp_lines.quantity, 1.0)
        self.assertEqual(stamp_lines.price_unit, 0.0)

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
            lambda line: self.stamp_tax_purchase in line.tax_ids
        )

        self.assertEqual(len(stamp_lines), 1)
