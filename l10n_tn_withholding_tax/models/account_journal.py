# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_withholding_tax_journal = fields.Boolean(
        string="Journal includes Withholding Tax",
    )

    withholding_tax_rate = fields.Float(string="Rate")
