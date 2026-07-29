# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_tn_withholding_tax_include_vat = fields.Boolean(
        string="Withholding includes VAT"
    )
