# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    tn_boe_journal = fields.Boolean(string="Tunisian Bills Journal", copy=False)
