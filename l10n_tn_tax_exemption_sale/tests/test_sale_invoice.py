# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, fields
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSaleInvoiceTaxExemption(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("tn")
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.country_id = cls.env.ref("base.tn")
        cls.partner_a.property_account_position_id = False
        cls.product_a.write(
            {
                "type": "service",
                "invoice_policy": "order",
                "taxes_id": [Command.set(cls.tax_sale_a.ids)],
            }
        )
        cls.exemption_position = cls.env["account.fiscal.position"].create(
            {"name": "Exemption", "company_id": cls.env.company.id}
        )
        cls.exemption_tax = cls.tax_sale_a.copy(
            {
                "name": "Exemption test tax",
                "amount": 0,
                "original_tax_ids": [Command.set(cls.tax_sale_a.ids)],
                "fiscal_position_ids": [Command.set(cls.exemption_position.ids)],
            }
        )
        cls.exemption = cls.env["l10n_tn.tax_exemption"].create(
            {
                "name": "TN certificate",
                "partner_id": cls.partner_a.id,
                "date_start": fields.Date.subtract(fields.Date.today(), months=1),
                "date_end": fields.Date.add(fields.Date.today(), months=1),
                "fiscal_position_id": cls.exemption_position.id,
            }
        )

    @classmethod
    def get_default_groups(cls):
        return super().get_default_groups() | cls.env.ref(
            "sales_team.group_sale_salesman"
        )

    def _create_order(self, fiscal_position):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "fiscal_position_id": fiscal_position.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "product_uom_qty": 1,
                            "price_unit": 100,
                        }
                    )
                ],
            }
        )
        order.action_confirm()
        return order

    def test_sale_invoice_applies_valid_exemption_and_taxes(self):
        order = self._create_order(self.env["account.fiscal.position"])
        self.assertEqual(order.order_line.tax_ids, self.tax_sale_a)

        invoice = order._create_invoices()

        self.assertFalse(invoice.invoice_date)
        self.assertTrue(invoice.l10n_tn_is_domestic_transaction)
        self.assertEqual(invoice.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.exemption_tax)
        self.assertEqual(invoice.amount_tax, 0)
        self.assertFalse(order.fiscal_position_id)
        self.assertEqual(order.order_line.tax_ids, self.tax_sale_a)

    def test_sale_invoice_drops_expired_exemption_and_restores_taxes(self):
        order = self._create_order(self.exemption_position)
        self.assertEqual(order.order_line.tax_ids, self.exemption_tax)

        self.exemption.date_end = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = order._create_invoices()

        self.assertFalse(invoice.l10n_tn_tax_exemption_id)
        self.assertFalse(invoice.fiscal_position_id)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax_sale_a)
        self.assertGreater(invoice.amount_tax, 0)
        self.assertEqual(order.fiscal_position_id, self.exemption_position)

    def test_sale_invoice_uses_partner_position_without_valid_exemption(self):
        partner_position = self.env["account.fiscal.position"].create(
            {"name": "Customer position", "company_id": self.env.company.id}
        )
        # an empty fiscal position removes all taxes in Odoo 19
        self.tax_sale_a.fiscal_position_ids = [Command.link(partner_position.id)]
        self.partner_a.property_account_position_id = partner_position
        order = self._create_order(self.exemption_position)

        self.exemption.date_end = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = order._create_invoices()

        self.assertFalse(invoice.l10n_tn_tax_exemption_id)
        self.assertEqual(invoice.fiscal_position_id, partner_position)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax_sale_a)

    def test_grouped_orders_recompute_invoice_position(self):
        orders = self._create_order(self.env["account.fiscal.position"])
        orders |= self._create_order(self.env["account.fiscal.position"])

        invoice = orders._create_invoices()

        self.assertEqual(len(invoice), 1)
        self.assertFalse(invoice.invoice_date)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.exemption_tax)
        self.assertEqual(invoice.amount_tax, 0)

    def test_down_payment_invoice_recomputes_position(self):
        order = self._create_order(self.env["account.fiscal.position"])
        wizard = self.env["sale.advance.payment.inv"].create(
            {
                "sale_order_ids": [Command.set(order.ids)],
                "advance_payment_method": "percentage",
                "amount": 50,
            }
        )

        invoice = wizard._create_invoices(order)

        self.assertFalse(invoice.invoice_date)
        self.assertTrue(invoice.l10n_tn_is_domestic_transaction)
        self.assertEqual(invoice.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)
        product_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertEqual(product_lines.tax_ids, self.exemption_tax)
        self.assertEqual(invoice.amount_tax, 0)

    def test_sale_invoice_uses_explicit_date_instead_of_today(self):
        self.exemption.write({"date_start": "2024-01-01", "date_end": "2024-12-31"})
        order = self._create_order(self.env["account.fiscal.position"])
        values = order._prepare_invoice()
        values.update(
            invoice_date="2024-06-15",
            invoice_line_ids=[
                Command.create(line._prepare_invoice_line())
                for line in order.order_line
            ],
        )

        invoice = self.env["account.move"].create(values)

        self.assertEqual(str(invoice.invoice_date), "2024-06-15")
        self.assertEqual(invoice.l10n_tn_tax_exemption_id, self.exemption)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.exemption_tax)
        self.assertEqual(invoice.amount_tax, 0)

    def test_manual_invoice_keeps_explicit_position(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.subtract(fields.Date.today(), years=1),
                "fiscal_position_id": self.exemption_position.id,
                "invoice_line_ids": [
                    Command.create({"product_id": self.product_a.id, "price_unit": 100})
                ],
            }
        )

        self.assertFalse(invoice.l10n_tn_tax_exemption_id)
        self.assertEqual(invoice.fiscal_position_id, self.exemption_position)
