# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_tn_is_productless_downpayment(self):
        self.ensure_one()
        return (
            self.is_downpayment
            and self.display_type == "product"
            and not self.product_id
            and bool(self.sale_line_ids)
            and self.company_id.chart_template == "tn"
            and self.move_id.state == "draft"
            and self.move_id.is_sale_document()
        )

    def _get_computed_taxes(self):
        self.ensure_one()
        if not self._l10n_tn_is_productless_downpayment():
            return super()._get_computed_taxes()
        # down payments inherit mapped order taxes, recover their sources first
        taxes = self.env["account.tax"]
        for tax in self.sale_line_ids.tax_ids:
            taxes |= tax.original_tax_ids or tax
        return self.move_id.fiscal_position_id.map_tax(taxes)

    def _compute_tax_ids(self):
        res = super()._compute_tax_ids()
        for line in self.filtered(
            lambda line: line._l10n_tn_is_productless_downpayment()
        ):
            # the standard computation preserves taxes on productless lines
            line.tax_ids = line._get_computed_taxes()
        return res
