# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    @api.constrains("journal_id", "payment_method_id", "payment_account_id")
    def _check_withholding_account(self):
        for method in self:
            journal = method.journal_id
            if (
                journal.is_withholding_tax_journal
                and method.payment_type == journal.withholding_direction
                and method.payment_account_id
            ):
                journal._check_withholding_account(method.payment_account_id)
