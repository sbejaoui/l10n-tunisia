from odoo import Command
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..hooks import post_init_hook


@tagged("post_install", "-at_install")
class TestAccountMove(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("tn")
    def setUpClass(cls):
        super().setUpClass()
        tn = cls.env.ref("base.tn")
        cls.partner_a.country_id = tn
        chart = cls.env["account.chart.template"]
        cls.stamp_tax_sale = chart.ref("l10n_tn_tax_vat_sale_tax_stamp")
        cls.stamp_tax_purchase = chart.ref("l10n_tn_tax_vat_purchase_tax_stamp")

    @classmethod
    def _create_stamp_tax(cls, type_tax_use):
        return cls.env["account.tax"].create(
            {
                "name": f"Stamp Tax {type_tax_use}",
                "amount_type": "fixed",
                "amount": 1.0,
                "type_tax_use": type_tax_use,
                "l10n_tn_is_stamp_tax": True,
                "company_id": cls.company_data["company"].id,
                "country_id": cls.company_data["company"].account_fiscal_country_id.id,
            }
        )

    def _create_invoice(self, move_type="out_invoice", partner=None):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": (partner or self.partner_a).id,
                "invoice_date": "2024-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 1,
                            "price_unit": 100,
                        }
                    )
                ],
            }
        )

    def _is_stamp_tax_exist(self, invoice):
        return bool(invoice.invoice_line_ids.filtered("l10n_tn_is_stamp_tax"))

    def test_stamp_tax_addition(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.assertTrue(self._is_stamp_tax_exist(invoice))

    def test_chart_stamp_taxes_are_configured(self):
        chart = self.env["account.chart.template"]
        for tax, account_xmlid in (
            (self.stamp_tax_sale, "l10n_tn_437"),
            (self.stamp_tax_purchase, "l10n_tn_6654"),
        ):
            with self.subTest(tax_type=tax.type_tax_use):
                self.assertTrue(tax.l10n_tn_is_stamp_tax)
                self.assertEqual(tax.amount_type, "fixed")
                self.assertEqual(tax.amount, 1.0)
                for lines in (
                    tax.invoice_repartition_line_ids,
                    tax.refund_repartition_line_ids,
                ):
                    self.assertEqual(
                        lines.filtered(
                            lambda line: line.repartition_type == "tax"
                        ).account_id,
                        chart.ref(account_xmlid),
                    )

    def test_installation_hook_configures_existing_chart_taxes(self):
        taxes = self.stamp_tax_sale | self.stamp_tax_purchase
        taxes.l10n_tn_is_stamp_tax = False
        self.stamp_tax_sale.name = "Configured stamp tax"
        original_count = self.env["account.tax"].search_count(
            [("company_id", "=", self.env.company.id)]
        )
        post_init_hook(self.env)
        post_init_hook(self.env)
        self.assertTrue(all(taxes.mapped("l10n_tn_is_stamp_tax")))
        self.assertEqual(self.stamp_tax_sale.name, "Configured stamp tax")
        self.assertEqual(
            self.env["account.tax"].search_count(
                [("company_id", "=", self.env.company.id)]
            ),
            original_count,
        )

    def test_installation_hook_preserves_manual_stamp_tax(self):
        self.stamp_tax_sale.l10n_tn_is_stamp_tax = False
        custom_tax = self._create_stamp_tax("sale")
        post_init_hook(self.env)
        self.assertFalse(self.stamp_tax_sale.l10n_tn_is_stamp_tax)
        self.assertEqual(
            self.env["account.tax"]._get_stamp_tax("sale", self.env.company.id),
            custom_tax,
        )

    def test_sale_invoice_has_one_stamp_tax_line(self):
        invoice = self._create_invoice()
        invoice.action_post()

        stamp_lines = invoice.invoice_line_ids.filtered("l10n_tn_is_stamp_tax")

        self.assertEqual(len(stamp_lines), 1)
        self.assertEqual(stamp_lines.quantity, 1.0)
        self.assertEqual(stamp_lines.price_unit, 0.0)
        self.assertEqual(stamp_lines.tax_ids, self.stamp_tax_sale)

    def test_stamp_tax_line_is_last(self):
        for move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type=move_type)
                invoice.invoice_line_ids.sequence = 1000
                invoice.invoice_line_ids = [
                    Command.create(
                        {
                            "display_type": "line_note",
                            "name": "Final note",
                            "sequence": 2000,
                        }
                    )
                ]
                invoice.action_post()
                stamp_line = invoice.invoice_line_ids.filtered("l10n_tn_is_stamp_tax")
                other_lines = invoice.invoice_line_ids - stamp_line
                self.assertEqual(len(stamp_line), 1)
                self.assertGreater(
                    stamp_line.sequence, max(other_lines.mapped("sequence"))
                )
                self.assertEqual(
                    invoice.invoice_line_ids.sorted("sequence")[-1], stamp_line
                )

    def test_no_stamp_tax_for_foreign_partner(self):
        foreign_partner = self.env["res.partner"].create(
            {
                "name": "Foreign Client",
                "country_id": self.env.ref("base.fr").id,
            }
        )
        invoice = self._create_invoice(partner=foreign_partner)
        invoice.action_post()

        self.assertFalse(self._is_stamp_tax_exist(invoice))

    def test_purchase_invoice_uses_purchase_stamp_tax(self):
        bill = self._create_invoice(move_type="in_invoice")
        bill.action_post()

        stamp_lines = bill.invoice_line_ids.filtered("l10n_tn_is_stamp_tax")

        self.assertEqual(len(stamp_lines), 1)
        self.assertEqual(stamp_lines.tax_ids, self.stamp_tax_purchase)

    def test_batch_post_invoices_adds_stamp_tax(self):
        invoices = self._create_invoice() | self._create_invoice()
        invoices.action_post()

        for invoice in invoices:
            self.assertTrue(self._is_stamp_tax_exist(invoice))
