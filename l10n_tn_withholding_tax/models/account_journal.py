# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_withholding_tax_journal = fields.Boolean(
        string="Journal includes Withholding Tax",
    )
    withholding_direction = fields.Selection(
        selection=[("inbound", "Incoming"), ("outbound", "Outgoing")],
        help="Incoming for customer withholding; outgoing for supplier withholding.",
    )
    withholding_tax_rate = fields.Float(string="Rate")

    @api.constrains("is_withholding_tax_journal", "withholding_direction")
    def _check_withholding_direction(self):
        for journal in self:
            if journal.is_withholding_tax_journal and not journal.withholding_direction:
                raise ValidationError(
                    self.env._("A withholding tax journal must have a direction.")
                )
