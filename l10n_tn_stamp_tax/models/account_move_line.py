from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_tn_is_stamp_tax = fields.Boolean(string="Is Stamp Tax")
