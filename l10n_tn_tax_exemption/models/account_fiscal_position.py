# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import UserError


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_tn_exemption(self):
        for position in self:
            exemption = (
                self.env["account.chart.template"]
                .with_company(position.company_id)
                .ref("fiscal_position_template_exo", raise_if_not_found=False)
            )
            if position == exemption:
                raise UserError(
                    self.env._(
                        "The Tunisian Exemption fiscal position cannot be deleted."
                    )
                )
