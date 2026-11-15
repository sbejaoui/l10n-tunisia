# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).

from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("tn", "account.tax.group")
    def _get_tn_fodec_account_tax_group(self):
        return self._parse_csv("tn", "account.tax.group", module="l10n_tn_fodec")

    @template("tn", "account.tax")
    def _get_tn_fodec_account_tax(self):
        return self._parse_csv("tn", "account.tax", module="l10n_tn_fodec")
