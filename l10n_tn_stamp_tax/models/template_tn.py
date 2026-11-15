# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).

from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("tn", "account.tax")
    def _get_tn_stamp_tax_account_tax(self):
        return {
            "l10n_tn_tax_vat_sale_tax_stamp": {"l10n_tn_is_stamp_tax": True},
            "l10n_tn_tax_vat_purchase_tax_stamp": {"l10n_tn_is_stamp_tax": True},
        }
