# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.onchange("journal_id")
    def _calculate_withholding_amount(self):
        if self.journal_id.is_withholding_tax_journal:
            total_amount = sum(move.amount_total for move in self.line_ids.move_id)
            withholding_amount = total_amount * self.journal_id.withholding_tax_rate
            self.amount = withholding_amount
        else:
            withholding_amount = 0.0
