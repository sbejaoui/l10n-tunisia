from odoo import Command
from odoo.tests.common import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestAccountMove(AccountTestInvoicingCommon):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tn = cls.env.ref("base.tn")
        cls.company_data['company'].country_id = tn
        cls.partner_a.country_id = tn

    def _create_invoice(self):
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
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
            
            