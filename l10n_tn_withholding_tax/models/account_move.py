# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

_WITHHOLDING_RECONCILIATION_DEPENDS = (
    "state",
    "move_type",
    "line_ids.account_id.account_type",
    "line_ids.matched_debit_ids.debit_move_id.move_id.state",
    "line_ids.matched_credit_ids.credit_move_id.move_id.state",
    "line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.state",
    "line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.state",
    "line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_withholding_tax_payment",
    "line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_withholding_tax_payment",
    "line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.withholding_reception_confirmed",
    "line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.withholding_reception_confirmed",
)


class AccountMove(models.Model):
    _inherit = "account.move"

    is_rs_eligible = fields.Boolean(
        string="RS Eligible",
        compute="_compute_is_rs_eligible",
    )
    is_rs_paid = fields.Boolean(
        string="RS Already Paid",
        compute="_compute_is_rs_paid",
    )
    withholding_certificate_pending = fields.Boolean(
        compute="_compute_withholding_status",
    )
    withholding_payment_count = fields.Integer(
        string="Withholding Payments",
        compute="_compute_withholding_status",
    )

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
        *_WITHHOLDING_RECONCILIATION_DEPENDS,
    )
    def _compute_payment_state(self):
        result = super()._compute_payment_state()
        for move in self:
            if move.payment_state == "paid" and any(
                payment.is_withholding_tax_payment
                and payment.state == "in_process"
                and not payment.is_matched
                for payment in move._get_reconciled_withholding_payments()
            ):
                # community normally skips the in_payment state
                move.payment_state = "in_payment"
        return result

    @api.depends("amount_total")
    def _compute_is_rs_eligible(self):
        for move in self:
            move.is_rs_eligible = move.amount_total >= 1000

    @api.depends(*_WITHHOLDING_RECONCILIATION_DEPENDS)
    def _compute_is_rs_paid(self):
        for move in self:
            move.is_rs_paid = bool(move._get_reconciled_withholding_payments())

    @api.depends(*_WITHHOLDING_RECONCILIATION_DEPENDS)
    def _compute_withholding_status(self):
        for move in self:
            payments = move._get_reconciled_withholding_payments()
            move.withholding_payment_count = len(payments)
            move.withholding_certificate_pending = any(
                not payment.withholding_reception_confirmed for payment in payments
            )

    def action_view_withholding_payments(self):
        self.check_access("read")
        payments = self.env["account.payment"]
        for move in self:
            payments |= move._get_reconciled_withholding_payments()
        payments.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Withholding Payments"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "views": [
                (
                    self.env.ref(
                        "l10n_tn_withholding_tax.view_withholding_payment_list"
                    ).id,
                    "list",
                ),
                (False, "form"),
            ],
            "search_view_id": self.env.ref(
                "l10n_tn_withholding_tax.view_withholding_payment_search"
            ).id,
            "domain": [("id", "in", payments.ids)],
            "context": {"create": False},
        }

    def _get_reconciled_withholding_payments(self):
        self.ensure_one()
        if self.state != "posted" or self.move_type not in (
            "out_invoice",
            "in_invoice",
        ):
            return self.env["account.payment"]
        counterpart_lines = self.line_ids.filtered(
            lambda line: (
                line.account_id.account_type
                in ("asset_receivable", "liability_payable")
            )
        )
        partials = (
            counterpart_lines.matched_debit_ids | counterpart_lines.matched_credit_ids
        )
        payments = (
            partials.debit_move_id | partials.credit_move_id
        ).move_id.origin_payment_id
        return payments.filtered(
            lambda payment: (
                payment.is_withholding_tax_payment
                and payment.state in ("in_process", "paid")
                and payment.move_id.state == "posted"
            )
        )

    def is_withholding_tax_rule_applied(self, rule):
        self.ensure_one()
        return rule.withholding_journal_id in (
            self._get_reconciled_withholding_payments().journal_id
        )

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
