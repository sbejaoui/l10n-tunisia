# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


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
        if any(
            not payment.is_withholding_tax_payment
            or payment.state != "in_process"
            or payment.withholding_reception_confirmed
            for payment in self
        ):
            raise UserError(
                self.env._("Only pending withholding payments can be confirmed.")
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

    def write(self, vals):
        if vals.get("state") in ("draft", "canceled", "rejected"):
            vals = dict(
                vals,
                withholding_reception_confirmed=False,
                withholding_reception_date=False,
                withholding_reception_user_id=False,
            )
        return super().write(vals)
