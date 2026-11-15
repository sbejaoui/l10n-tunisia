# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_tn_tax_exemption_reminder_months = fields.Integer(
        related="company_id.l10n_tn_tax_exemption_reminder_months",
        readonly=False,
    )
