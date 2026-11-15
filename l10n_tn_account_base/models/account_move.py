# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_tn_is_domestic_transaction = fields.Boolean(
        string="Tunisian Domestic Transaction",
        compute="_compute_l10n_tn_is_domestic_transaction",
    )

    def _l10n_tn_is_domestic_transaction(self):
        self.ensure_one()
        return (
            self.company_id.country_id.code == "TN"
            and self.partner_id.country_id.code == "TN"
        )

    @api.depends("company_id.country_id.code", "partner_id.country_id.code")
    def _compute_l10n_tn_is_domestic_transaction(self):
        for move in self:
            move.l10n_tn_is_domestic_transaction = (
                move._l10n_tn_is_domestic_transaction()
            )
