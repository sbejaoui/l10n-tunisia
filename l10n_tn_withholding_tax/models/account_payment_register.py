# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


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

    def _get_withholding_amount(self, journal):
        self.ensure_one()
        if not journal.is_withholding_tax_journal:
            return 0.0
        total = sum(self.line_ids.move_id.mapped("amount_total"))
        return total * journal.withholding_tax_rate

    @api.depends("line_ids")
    def _compute_withholding_tax_alert(self):
        for record in self:
            invoices = record.line_ids.move_id
            currency = invoices.currency_id
            rules = self.env["l10n.tn.withholding.rule"]._get_applicable_rules(invoices)

            if rules:
                message = "Applicable withholding rules:\n"
                for rule in rules:
                    amount = record._get_withholding_amount(rule.withholding_journal_id)
                    formatted_price = formatLang(
                        self.env, amount, currency_obj=currency
                    )
                    message += (
                        f"- {rule.product_id.name}:"
                        + f" {rule.withholding_journal_id.name}"
                        + f" ({formatted_price})\n"
                    )
                record.withholding_tax_alert = message
            else:
                record.withholding_tax_alert = False

    @api.onchange("journal_id")
    def _check_withholding_tax_already_paid(self):
        if not self.journal_id.is_withholding_tax_journal:
            return

        payments = self.line_ids.move_id.matched_payment_ids

        if any(payment.journal_id == self.journal_id for payment in payments):
            raise UserError(_("This withholding tax has already been paid."))
