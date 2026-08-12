# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class TaxExemption(models.Model):
    _name = "l10n_tn.tax_exemption"
    _description = "Tax Exemption"

    name = fields.Char()
    partner_id = fields.Many2one("res.partner", string="Partner")
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position", string="Fiscal Position"
    )
