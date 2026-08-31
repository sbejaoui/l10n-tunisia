# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    is_rs_eligible = fields.Boolean(
        string="RS Eligible",
        compute="_compute_is_rs_eligible",
    )

    @api.depends("amount_total")
    def _compute_is_rs_eligible(self):
        for move in self:
            move.is_rs_eligible = move.amount_total >= 1000
