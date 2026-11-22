# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        self.origin_payment_id._check_withholding_configuration()
        return super()._post(soft=soft)

    @api.depends(
        "amount_residual",
        "move_type",
        "state",
        "company_id",
        "reconciled_payment_ids.state",
        "matched_payment_ids.state",
        "matched_payment_ids.is_matched",
        "matched_payment_ids.is_withholding_tax_payment",
    )
    def _compute_payment_state(self):
        result = super()._compute_payment_state()
        for move in self:
            if move.payment_state == "paid" and any(
                payment.is_withholding_tax_payment
                and payment.state == "in_process"
                and not payment.is_matched
                for payment in move.matched_payment_ids
            ):
                # community normally skips the in_payment state
                move.payment_state = "in_payment"
        return result

    is_rs_eligible = fields.Boolean(
        string="RS Eligible",
        compute="_compute_is_rs_eligible",
    )

    @api.depends("amount_total")
    def _compute_is_rs_eligible(self):
        for move in self:
            move.is_rs_eligible = move.amount_total >= 1000

    is_rs_paid = fields.Boolean(
        string="RS Already Paid",
        compute="_compute_is_rs_paid",
    )

    @api.depends(
        "matched_payment_ids.state",
        "matched_payment_ids.journal_id.is_withholding_tax_journal",
    )
    def _compute_is_rs_paid(self):
        for move in self:
            rs_paid = False
            for payment in move.matched_payment_ids:
                if payment.journal_id.is_withholding_tax_journal and payment.state in (
                    "in_process",
                    "paid",
                ):
                    rs_paid = True
            move.is_rs_paid = rs_paid

    def is_withholding_tax_rule_applied(self, rule):
        self.ensure_one()

        for payment in self.matched_payment_ids:
            if payment.journal_id == rule.withholding_journal_id and payment.state in (
                "in_process",
                "paid",
            ):
                return True

        return False

    def _is_withholding_tax_applicable(self):
        self.ensure_one()
        return self.l10n_tn_is_domestic_transaction

    def _get_withholding_invoice_report_payments(self):
        self.ensure_one()
        payments = (self.invoice_payments_widget or {}).get("content", [])
        withholding_payment_ids = set(
            self.env["account.payment"]
            .browse(
                [
                    payment["account_payment_id"]
                    for payment in payments
                    if payment.get("account_payment_id")
                ]
            )
            .filtered("is_withholding_tax_payment")
            .ids
        )
        report_payments = [
            dict(
                payment,
                is_withholding_tax_payment=(
                    payment.get("account_payment_id") in withholding_payment_ids
                ),
            )
            for payment in payments
        ]
        return sorted(
            report_payments,
            key=lambda payment: not payment["is_withholding_tax_payment"],
        )
