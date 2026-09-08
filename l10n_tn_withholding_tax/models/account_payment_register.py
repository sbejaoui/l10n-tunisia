# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    withholding_tax_alert = fields.Text(compute="_compute_withholding_tax_alert")

    @api.onchange("journal_id")
    def _calculate_withholding_amount(self):
        if self.journal_id.is_withholding_tax_journal:
            total_amount = sum(move.amount_total for move in self.line_ids.move_id)
            withholding_amount = total_amount * self.journal_id.withholding_tax_rate
            self.amount = withholding_amount
        else:
            withholding_amount = 0.0

    # @api.depends("line_ids")
    # def _compute_withholding_tax_alert(self):
    #     for record in self:
    #         record.withholding_tax_alert = "TEST MESSAGE"

    @api.depends("line_ids")
    def _compute_withholding_tax_alert(self):
        for record in self:
            invoices = record.line_ids.move_id
            rules = self.env["l10n.tn.withholding.rule"]._get_applicable_rules(invoices)

            if rules:
                message = "Applicable withholding rules:\n"
                for rule in rules:
                    message += (
                        f"- {rule.product_id.name}:"
                        + f"{rule.withholding_journal_id.name}\n"
                    )
                record.withholding_tax_alert = message
            else:
                record.withholding_tax_alert = False
