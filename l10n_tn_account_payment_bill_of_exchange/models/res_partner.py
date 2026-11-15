# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_tn_bills(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_tn_account_payment_bill_of_exchange.action_boe"
        )
        action["domain"] = [
            ("tn_boe", "=", True),
            ("partner_id", "child_of", self.commercial_partner_id.id),
        ]
        return action
