# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_tn_journal_include_withholding = fields.Boolean(
        string="Journal includes Withholding Tax",
    )

    l10n_tn_journal_amount = fields.Float(string="Amount")
