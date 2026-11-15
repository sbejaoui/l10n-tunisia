# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_tn_tax_exemption_reminder_months = fields.Integer(
        string="Tax Exemption Reminder Period (Months)",
        default=12,
        help="Warn when a customer's exemption expired within this many months "
        "before the invoice date. Set to 0 to disable reminders.",
    )

    _tax_exemption_reminder_months_nonnegative = models.Constraint(
        "CHECK(l10n_tn_tax_exemption_reminder_months >= 0)",
        "The tax exemption reminder period cannot be negative.",
    )
