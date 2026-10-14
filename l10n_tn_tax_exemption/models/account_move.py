# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_tn_tax_exemption_id = fields.Many2one(
        "l10n_tn.tax_exemption",
        string="Tax Exemption",
        ondelete="restrict",
        compute="_compute_l10n_tn_tax_exemption_id",
        store=True,
        readonly=False,
    )

    @api.depends("commercial_partner_id", "invoice_date")
    def _compute_l10n_tn_tax_exemption_id(self):
        for move in self:
            date = move.invoice_date or fields.Date.context_today(move)
            move.l10n_tn_tax_exemption_id = self.env["l10n_tn.tax_exemption"].search(
                [
                    ("partner_id", "=", move.commercial_partner_id.id),
                    ("date_start", "<=", date),
                    ("date_end", ">=", date),
                ],
                limit=1,
            )

    @api.depends("l10n_tn_tax_exemption_id")
    def _compute_fiscal_position_id(self):
        res = super()._compute_fiscal_position_id()
        for move in self:
            exemption = move.l10n_tn_tax_exemption_id
            if exemption:
                move.fiscal_position_id = exemption.fiscal_position_id
        return res
