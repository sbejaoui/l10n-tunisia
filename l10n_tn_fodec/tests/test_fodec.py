# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..hooks import post_init_hook


@tagged("post_install", "-at_install")
class TestFodec(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("tn")
    def setUpClass(cls):
        super().setUpClass()
        cls.chart = cls.env["account.chart.template"]
        cls.fodec_sale = cls.chart.ref("l10n_tn_tax_fodec_sale")
        cls.fodec_purchase = cls.chart.ref("l10n_tn_tax_fodec_purchase")
        cls.vat_sale = cls.chart.ref("l10n_tn_tax_vat_sale_19")

    def test_fodec_increases_vat_base_on_sales_and_refunds(self):
        for is_refund in (False, True):
            with self.subTest(is_refund=is_refund):
                result = (self.fodec_sale | self.vat_sale).compute_all(
                    100, currency=self.env.company.currency_id, is_refund=is_refund
                )
                amounts = {tax["id"]: tax for tax in result["taxes"]}
                self.assertAlmostEqual(amounts[self.fodec_sale.id]["amount"], 1)
                self.assertAlmostEqual(amounts[self.vat_sale.id]["base"], 101)
                self.assertAlmostEqual(amounts[self.vat_sale.id]["amount"], 19.19)
                self.assertAlmostEqual(result["total_included"], 120.19)
                self.assertEqual(
                    amounts[self.fodec_sale.id]["account_id"],
                    self.chart.ref("l10n_tn_43658").id,
                )

    def test_purchase_fodec_is_a_cost_and_increases_vat_base(self):
        vat = self.chart.ref("l10n_tn_tax_vat_purchase_19_other_local")
        result = (self.fodec_purchase | vat).compute_all(
            100, currency=self.env.company.currency_id
        )
        amounts = {tax["id"]: tax for tax in result["taxes"]}
        self.assertAlmostEqual(amounts[vat.id]["base"], 101)
        self.assertAlmostEqual(result["total_included"], 120.19)
        self.assertFalse(amounts[self.fodec_purchase.id]["account_id"])

    def test_export_exempts_fodec(self):
        export = self.chart.ref("l10n_tn_fp_template_export")
        taxes = export.map_tax(self.fodec_sale | self.vat_sale)
        self.assertNotIn(self.fodec_sale, taxes)
        self.assertIn(self.chart.ref("l10n_tn_tax_fodec_sale_export"), taxes)
        result = taxes.compute_all(100, currency=self.env.company.currency_id)
        self.assertAlmostEqual(result["total_included"], 100)

    def test_installation_hook_preserves_existing_tax_configuration(self):
        original_ids = (self.fodec_sale | self.fodec_purchase).ids
        self.fodec_sale.name = "Configured FODEC"
        post_init_hook(self.env)
        self.assertEqual(
            (
                self.chart.ref("l10n_tn_tax_fodec_sale")
                | self.chart.ref("l10n_tn_tax_fodec_purchase")
            ).ids,
            original_ids,
        )
        self.assertEqual(self.fodec_sale.name, "Configured FODEC")
