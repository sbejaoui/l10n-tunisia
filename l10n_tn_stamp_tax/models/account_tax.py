from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_tn_is_stamp_tax = fields.Boolean(string="Is Stamp Tax")
