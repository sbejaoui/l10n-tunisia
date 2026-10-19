# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError

PROTECTED_FIELDS = {
    "name",
    "partner_id",
    "date_start",
    "date_end",
    "fiscal_position_id",
}


class TaxExemption(models.Model):
    _name = "l10n_tn.tax_exemption"
    _description = "Tax Exemption"

    name = fields.Char()
    partner_id = fields.Many2one("res.partner", string="Partner")
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position",
        domain=[("tax_ids", "!=", False)],
    )
    l10n_tn_tax_exemption_file = fields.Binary(
        string="Tax Exemption File",
        attachment=True,
        copy=False,
    )
    l10n_tn_tax_exemption_filename = fields.Char(copy=False)
    move_ids = fields.One2many(
        "account.move",
        "l10n_tn_tax_exemption_id",
        string="Invoices",
    )
    move_count = fields.Integer(
        string="Invoices count",
        compute="_compute_move_count",
    )

    @api.depends("move_ids")
    def _compute_move_count(self):
        for exemption in self:
            exemption.move_count = len(exemption.move_ids)

    def _check_not_used(self):
        for exemption in self:
            if exemption.move_ids:
                raise UserError(
                    self.env._(
                        "Tax exemption %(name)s is already used by %(count)s "
                        "invoice(s) and can no longer be modified or deleted. "
                        "Create a new tax exemption instead.",
                        name=exemption.display_name,
                        count=len(exemption.move_ids),
                    )
                )

    def write(self, vals):
        if not PROTECTED_FIELDS.isdisjoint(vals):
            self._check_not_used()
        return super().write(vals)

    def unlink(self):
        self._check_not_used()
        return super().unlink()
