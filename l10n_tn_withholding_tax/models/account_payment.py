# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_withholding_tax_payment = fields.Boolean(
        related="journal_id.is_withholding_tax_journal",
    )
    withholding_reception_confirmed = fields.Boolean(
        string="Certificate Confirmed",
        readonly=True,
        copy=False,
        tracking=True,
    )
    withholding_reception_date = fields.Datetime(
        string="Certificate Confirmation Date",
        readonly=True,
        copy=False,
        tracking=True,
    )
    withholding_reception_user_id = fields.Many2one(
        "res.users",
        string="Certificate Confirmed By",
        readonly=True,
        copy=False,
        tracking=True,
    )

    @api.depends(
        "reconciled_invoice_ids.payment_state",
        "move_id.line_ids.amount_residual",
        "is_withholding_tax_payment",
        "withholding_reception_confirmed",
    )
    def _compute_state(self):
        withholding = self.filtered("is_withholding_tax_payment")
        result = super(AccountPayment, self - withholding)._compute_state()
        for payment in withholding:
            if not payment.state:
                payment.state = "draft"
            elif payment.state in ("in_process", "paid"):
                payment.state = (
                    "paid" if payment.withholding_reception_confirmed else "in_process"
                )
        return result

    @api.depends(
        "move_id.line_ids.amount_residual",
        "move_id.line_ids.amount_residual_currency",
        "move_id.line_ids.account_id",
        "state",
        "is_withholding_tax_payment",
        "withholding_reception_confirmed",
    )
    def _compute_reconciliation_status(self):
        result = super()._compute_reconciliation_status()
        for payment in self.filtered("is_withholding_tax_payment"):
            # certificate confirmation replaces bank matching for withholding only
            payment.is_matched = (
                payment.withholding_reception_confirmed and payment.state == "paid"
            )
        return result

    def action_validate_withholding(self):
        if not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(
                self.env._("Only accounting users can confirm certificates.")
            )
        self.check_access("write")
        self._check_withholding_country()
        if any(
            not payment.is_withholding_tax_payment
            or payment.state != "in_process"
            or payment.withholding_reception_confirmed
            for payment in self
        ):
            raise UserError(
                self.env._("Only pending withholding payments can be confirmed.")
            )
        if any(
            not payment.move_id or payment.move_id.state != "posted" for payment in self
        ):
            raise UserError(
                self.env._("Certificate confirmation requires a posted journal entry.")
            )
        self.write(
            {
                "withholding_reception_confirmed": True,
                "withholding_reception_date": fields.Datetime.now(),
                "withholding_reception_user_id": self.env.user.id,
            }
        )
        return True

    def action_validate(self):
        withholding = self.filtered("is_withholding_tax_payment")
        if withholding:
            withholding.action_validate_withholding()
        return super(AccountPayment, self - withholding).action_validate()

    @api.constrains("journal_id", "company_id", "partner_id", "invoice_ids")
    def _check_withholding_country(self):
        for payment in self.filtered("is_withholding_tax_payment"):
            # use the shared invoice check for standalone payments as well
            transaction = self.env["account.move"].new(
                {
                    "company_id": payment.company_id.id,
                    "partner_id": payment.partner_id.id,
                }
            )
            if not transaction.l10n_tn_is_domestic_transaction or any(
                not invoice._is_withholding_tax_applicable()
                for invoice in payment.invoice_ids
            ):
                raise ValidationError(
                    self.env._(
                        "Tunisian withholding requires both the company and "
                        "the invoice partner to be based in Tunisia."
                    )
                )

    @api.constrains("journal_id", "payment_type", "partner_type", "invoice_ids")
    def _check_withholding_refund(self):
        for payment in self.filtered("is_withholding_tax_payment"):
            if (payment.partner_type, payment.payment_type) in (
                ("customer", "outbound"),
                ("supplier", "inbound"),
            ) or any(
                invoice.move_type in ("out_refund", "in_refund")
                for invoice in payment.invoice_ids
            ):
                raise ValidationError(
                    self.env._(
                        "New withholding payments are not supported for refunds. "
                        "Use a regular bank or cash payment."
                    )
                )

    def action_post(self):
        self._check_withholding_country()
        self._check_withholding_refund()
        self._check_withholding_configuration()
        return super().action_post()

    def _get_withholding_payment_account(self):
        self.ensure_one()
        self.journal_id._check_withholding_configuration()
        account = self.payment_method_line_id.payment_account_id
        self.journal_id._check_withholding_account(account)
        if account.currency_id and account.currency_id != self.currency_id:
            raise ValidationError(
                self.env._(
                    "The withholding fiscal account currency must match "
                    "the payment currency."
                )
            )
        return account

    @api.constrains(
        "journal_id",
        "outstanding_account_id",
        "move_id",
        "currency_id",
    )
    def _check_withholding_configuration(self):
        for payment in self.filtered("is_withholding_tax_payment"):
            outstanding_account = payment.outstanding_account_id
            account = payment._get_withholding_payment_account()
            if outstanding_account != account:
                raise ValidationError(
                    self.env._(
                        "A withholding payment must use the fiscal account "
                        "configured on its payment method."
                    )
                )
            if payment.move_id:
                liquidity, _counterpart, _writeoff = payment._seek_for_lines()
                if liquidity.account_id != account:
                    raise ValidationError(
                        self.env._(
                            "The withholding journal entry must use "
                            "the configured fiscal account."
                        )
                    )

    def _get_outstanding_account(self, payment_type):
        if self.is_withholding_tax_payment:
            return self._get_withholding_payment_account()
        return super()._get_outstanding_account(payment_type)

    @api.constrains(
        "state",
        "withholding_reception_confirmed",
        "withholding_reception_date",
        "withholding_reception_user_id",
    )
    def _check_inactive_withholding_confirmation(self):
        for payment in self.filtered("is_withholding_tax_payment"):
            if payment.state in ("draft", "canceled", "rejected") and (
                payment.withholding_reception_confirmed
                or payment.withholding_reception_date
                or payment.withholding_reception_user_id
            ):
                raise ValidationError(
                    self.env._(
                        "A draft, canceled or rejected withholding payment "
                        "cannot retain certificate confirmation."
                    )
                )

    @api.constrains(
        "journal_id",
        "move_id",
        "withholding_reception_confirmed",
        "withholding_reception_date",
        "withholding_reception_user_id",
    )
    def _check_withholding_certificate(self):
        for payment in self:
            if not (
                payment.withholding_reception_confirmed
                or payment.withholding_reception_date
                or payment.withholding_reception_user_id
            ):
                continue
            if (
                not payment.is_withholding_tax_payment
                or not payment.withholding_reception_confirmed
                or not payment.withholding_reception_date
                or not payment.withholding_reception_user_id
                or not payment.move_id
                or payment.move_id.state != "posted"
            ):
                raise ValidationError(
                    self.env._(
                        "A confirmed certificate requires a withholding payment "
                        "with a posted journal entry, confirmation date and user."
                    )
                )

    def _reset_withholding_confirmation(self):
        payments = self.filtered(
            lambda payment: (
                payment.is_withholding_tax_payment
                and (
                    payment.withholding_reception_confirmed
                    or payment.withholding_reception_date
                    or payment.withholding_reception_user_id
                )
            )
        )
        payments.write(
            {
                "withholding_reception_confirmed": False,
                "withholding_reception_date": False,
                "withholding_reception_user_id": False,
            }
        )

    def action_draft(self):
        self._reset_withholding_confirmation()
        return super().action_draft()

    def action_cancel(self):
        self._reset_withholding_confirmation()
        return super().action_cancel()

    def action_reject(self):
        self._reset_withholding_confirmation()
        return super().action_reject()
