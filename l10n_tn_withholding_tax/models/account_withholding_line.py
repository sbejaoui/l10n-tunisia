# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class AccountWithholdingLine(models.AbstractModel):
    _inherit = "account.withholding.line"

    def _compute_original_amounts(self):
        res = super()._compute_original_amounts()
        for line in self:
            if line.tax_id.l10n_tn_withholding_tax_include_vat:
                line.original_base_amount = line.comodel_currency_id.round(
                    line.original_base_amount * 1.19
                )
                line.original_tax_amount = line.comodel_currency_id.round(
                    line.original_tax_amount * 1.19
                )
        return res
