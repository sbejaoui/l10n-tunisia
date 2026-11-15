# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("tn", "account.tax.group")
    def _get_tn_tax_exemption_account_tax_group(self):
        return self._parse_csv(
            "tn", "account.tax.group", module="l10n_tn_tax_exemption"
        )

    @template("tn", "account.tax")
    def _get_tn_tax_exemption_account_tax(self):
        return self._parse_csv("tn", "account.tax", module="l10n_tn_tax_exemption")

    def _post_load_data(self, template_code, company, template_data):
        res = super()._post_load_data(template_code, company, template_data)
        if template_code == "tn":
            self._remove_tn_export_tax_from_exemption()
        return res

    def _remove_tn_export_tax_from_exemption(self):
        # chart reloads preserve links, remove the export tax from exemption explicitly
        self.ref("l10n_tn_tax_vat_sale_0").write(
            {
                "fiscal_position_ids": [
                    Command.unlink(self.ref("fiscal_position_template_exo").id),
                ],
            }
        )
