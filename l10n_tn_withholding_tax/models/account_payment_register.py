# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    withholding_tax_alert = fields.Text(compute="_compute_withholding_tax_alert")
    has_multiple_bills = fields.Boolean(compute="_compute_has_multiple_bills")
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
                    net_amount = rule._get_net_amount(invoices)
                    formatted_net = formatLang(
                        self.env, net_amount, currency_obj=currency
                    )
                    message += rule._get_withholding_alert_message(
                        amount, currency, invoices
                    )
                    message += _(
                        "  Amount after withholding: %(amount)s\n",
                        amount=formatted_net,
                    )
                record.withholding_tax_alert = message
            else:
                record.withholding_tax_alert = False

    @api.depends("line_ids")
    def _compute_has_multiple_bills(self):
        for record in self:
            record.has_multiple_bills = len(record.line_ids.move_id) > 1

    @api.depends("journal_id", "has_multiple_bills")
    def _compute_multiple_bills_alert(self):
        for record in self:
            if (
                record.journal_id.is_withholding_tax_journal
                and record.has_multiple_bills
            ):
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

    def _create_payments(self):
        self.ensure_one()

        if not (self.journal_id.is_withholding_tax_journal and self.has_multiple_bills):
            return super()._create_payments()

        payments = self.env["account.payment"]

        for bill in self.line_ids.move_id:
            payment_wizard = (
                self.env["account.payment.register"]
                .with_context(
                    active_model="account.move",
                    active_ids=[bill.id],
                )
                .create({})
            )

            payment_wizard.journal_id = self.journal_id
            payment_wizard.payment_date = self.payment_date
            payment_wizard.payment_method_line_id = self.payment_method_line_id
            payment_wizard._calculate_withholding_amount()

            payments |= payment_wizard._create_payments()

        return payments

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
