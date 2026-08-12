# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_tn_tax_exemption_ids = fields.One2many(
        "l10n_tn.tax_exemption",
        "partner_id",
        string="Tax Exemptions",
    )
