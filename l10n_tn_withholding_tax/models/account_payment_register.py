# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    withholding_tax_alert = fields.Text(compute="_compute_withholding_tax_alert")
    multiple_bills_alert = fields.Text(compute="_compute_multiple_bills_alert")

    @api.onchange("journal_id")
    def _calculate_withholding_amount(self):
        if self.journal_id.is_withholding_tax_journal:
            total_amount = sum(move.amount_total for move in self.line_ids.move_id)
            withholding_amount = total_amount * self.journal_id.withholding_tax_rate
            self.amount = withholding_amount
        else:
            withholding_amount = 0.0

    @api.depends("line_ids")
    def _compute_withholding_tax_alert(self):
        for record in self:
            invoices = record.line_ids.move_id
            currency = invoices.currency_id
            rules = self.env["l10n.tn.withholding.rule"]._get_applicable_rules(invoices)

            if rules:
                message = "Applicable withholding rules:\n"
                for rule in rules:
                    amount = rule._get_withholding_amount(invoices)
                    message += rule._get_withholding_alert_message(
                        amount, currency, invoices
                    )
                record.withholding_tax_alert = message
            else:
                record.withholding_tax_alert = False

    @api.depends("journal_id", "line_ids")
    def _compute_multiple_bills_alert(self):
        for record in self:
            bills = record.line_ids.move_id

            if record.journal_id.is_withholding_tax_journal and len(bills) > 1:
                record.multiple_bills_alert = _(
                    "You are about to pay the withholding tax of multiple bills."
                )
            else:
                record.multiple_bills_alert = False

    @api.onchange("journal_id")
    def _check_withholding_tax_already_paid(self):
        if not self.journal_id.is_withholding_tax_journal:
            return

        payments = self.line_ids.move_id.matched_payment_ids

        if any(payment.journal_id == self.journal_id for payment in payments):
            raise UserError(_("This withholding tax has already been paid."))

    @api.depends("payment_type", "company_id", "can_edit_wizard")
    def _compute_available_journal_ids(self):
        res = super()._compute_available_journal_ids()
        for wizard in self:
            invoices = wizard.line_ids.move_id
            rules = self.env["l10n.tn.withholding.rule"]._get_applicable_rules(invoices)
            wizard.available_journal_ids = (
                wizard.available_journal_ids.filtered(
                    lambda j: not j.is_withholding_tax_journal
                )
                + rules.withholding_journal_id
            )

        return res
