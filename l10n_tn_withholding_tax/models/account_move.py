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

    is_rs_paid = fields.Boolean(
        string="RS Already Paid",
        compute="_compute_is_rs_paid",
    )

    @api.depends("matched_payment_ids")
    def _compute_is_rs_paid(self):
        for move in self:
            rs_paid = False
            for payment in move.matched_payment_ids:
                if payment.journal_id.is_withholding_tax_journal:
                    rs_paid = True
            move.is_rs_paid = rs_paid

    def is_withholding_tax_rule_applied(self, rule):
        self.ensure_one()

        for payment in self.matched_payment_ids:
            if payment.journal_id == rule.withholding_journal_id:
                return True

        return False
