# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .account_payment import BOE_OPERATION


class BoeSettlement(models.Model):
    _name = "l10n_tn.boe.settlement"
    _description = "Bill Collection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True
    _order = "date desc, id desc"
    _rec_name = "reference"

    bill_id = fields.Many2one(
        "account.payment",
        required=True,
        check_company=True,
        ondelete="restrict",
        index=True,
    )
    incident_id = fields.Many2one(
        "l10n_tn.boe.incident", check_company=True, ondelete="restrict", index=True
    )
    company_id = fields.Many2one(related="bill_id.company_id", store=True)
    currency_id = fields.Many2one(related="bill_id.currency_id", store=True)
    partner_id = fields.Many2one(related="bill_id.partner_id", store=True)
    responsible_id = fields.Many2one(related="bill_id.boe_user_id", store=True)
    amount = fields.Monetary(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    reference = fields.Char(required=True)
    payment_id = fields.Many2one(
        "account.payment", check_company=True, ondelete="restrict", copy=False
    )
    source_line_id = fields.Many2one(
        "account.move.line",
        required=True,
        check_company=True,
        ondelete="restrict",
        copy=False,
    )
    canceled = fields.Boolean(default=False, copy=False)
    reversal_move_id = fields.Many2one(
        "account.move", check_company=True, copy=False, ondelete="restrict"
    )
    state = fields.Selection(
        [
            ("pending", "Pending Confirmation"),
            ("confirmed", "Confirmed"),
            ("canceled", "Canceled"),
        ],
        compute="_compute_state",
        store=True,
        index=True,
    )
    collected_amount = fields.Monetary(compute="_compute_state", store=True)
    recovered_amount = fields.Monetary(compute="_compute_state", store=True)
    ready_to_confirm = fields.Boolean(compute="_compute_ready", store=True, index=True)

    _source_line_unique = models.Constraint(
        "unique(source_line_id)",
        "This payment credit already belongs to a bill collection.",
    )

    @api.depends(
        "state",
        "payment_id.state",
        "source_line_id.move_id.state",
        "source_line_id.move_id.origin_payment_id.state",
    )
    def _compute_ready(self):
        for settlement in self:
            payment = (
                settlement.payment_id
                or settlement.source_line_id.move_id.origin_payment_id
            )
            settlement.ready_to_confirm = (
                settlement.state == "pending"
                and settlement.source_line_id.move_id.state == "posted"
                and (
                    payment.state in ("in_process", "paid")
                    if payment
                    else bool(settlement.source_line_id.move_id.statement_line_id)
                )
            )

    @api.depends(
        "canceled",
        "source_line_id.matched_debit_ids",
        "source_line_id.matched_debit_ids.amount",
        "source_line_id.move_id.state",
        "incident_id",
        "amount",
        "source_line_id.move_id.reversal_move_ids.state",
    )
    def _compute_state(self):
        for settlement in self:
            reversed_source = (
                settlement.source_line_id.move_id.reversal_move_ids.filtered(
                    lambda move: move.state == "posted"
                )
            )
            target = (
                settlement.incident_id.invoice_line_id
                if settlement.incident_id
                else settlement.bill_id._seek_for_lines()[0]
            )
            matched = sum(
                settlement.source_line_id.matched_debit_ids.filtered_domain(
                    [
                        ("debit_move_id", "in", target.ids),
                    ]
                ).mapped("amount")
            )
            confirmed = (
                not settlement.canceled
                and not reversed_source
                and settlement.source_line_id.move_id.state == "posted"
                and settlement.currency_id.is_zero(matched - settlement.amount)
            )
            settlement.state = (
                "canceled"
                if settlement.canceled or reversed_source
                else "confirmed"
                if confirmed
                else "pending"
            )
            settlement.collected_amount = (
                settlement.amount if confirmed and not settlement.incident_id else 0
            )
            settlement.recovered_amount = (
                settlement.amount if confirmed and settlement.incident_id else 0
            )

    @api.constrains("bill_id", "incident_id", "source_line_id", "amount")
    def _check_source(self):
        for settlement in self:
            bill = settlement.bill_id
            account = (
                settlement.incident_id.return_line_id.account_id
                if settlement.incident_id
                else bill.outstanding_account_id
            )
            if (
                not bill.tn_boe
                or settlement.source_line_id.account_id != account
                or settlement.source_line_id.partner_id.commercial_partner_id
                != bill.partner_id.commercial_partner_id
                or settlement.source_line_id.currency_id != settlement.currency_id
                or settlement.source_line_id.balance >= 0
                or settlement.currency_id.compare_amounts(settlement.amount, 0) <= 0
                or (settlement.incident_id and settlement.incident_id.bill_id != bill)
            ):
                raise ValidationError(
                    self.env._("The collection source, principal and bill must match.")
                )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_accounting_history(self):
        raise UserError(self.env._("Collections must be canceled, not deleted."))

    def action_confirm(self):
        for settlement in self:
            settlement.bill_id._boe_check_accountant()
            settlement.bill_id._boe_lock()
            settlement.invalidate_recordset()
            if settlement.state != "pending":
                raise UserError(
                    self.env._("Only pending collections can be confirmed.")
                )
            source = settlement.source_line_id
            payment = settlement.payment_id or source.move_id.origin_payment_id
            if source.move_id.state != "posted" or (
                payment and payment.state not in ("in_process", "paid")
            ):
                raise UserError(
                    self.env._(
                        "Post a valid actual payment before confirming the bill "
                        "collection."
                    )
                )
            if not payment and not source.move_id.statement_line_id:
                raise UserError(
                    self.env._(
                        "Use a posted bank transaction or an actual payment as "
                        "evidence."
                    )
                )
            if (
                settlement.currency_id.compare_amounts(
                    -source.amount_residual, settlement.amount
                )
                != 0
            ):
                raise UserError(
                    self.env._(
                        "The source must have exactly the selected principal still "
                        "available."
                    )
                )
            target = (
                settlement.incident_id.invoice_line_id
                if settlement.incident_id
                else settlement.bill_id._seek_for_lines()[0]
            )
            if (
                settlement.currency_id.compare_amounts(
                    sum(target.mapped("amount_residual")), settlement.amount
                )
                < 0
            ):
                raise UserError(
                    self.env._("The collection exceeds the remaining principal.")
                )
            (target + source).with_context(tn_boe_operation=BOE_OPERATION).reconcile()
            # this action also confirms receipt manually, bank matching is optional
            if payment and payment.state != "paid":
                payment.with_context(tn_boe_operation=BOE_OPERATION).action_validate()
            settlement.sudo().message_post(
                body=self.env._("Collection confirmed against the actual payment.")
            )
            settlement.bill_id.message_post(
                body=self.env._(
                    "Collection confirmed: %(reference)s",
                    reference=settlement.reference,
                )
            )
        return True

    def action_cancel(self):
        for settlement in self:
            bill = settlement.bill_id
            bill._boe_check_accountant(manager=True)
            bill._boe_lock()
            settlement.invalidate_recordset()
            if settlement.state == "canceled":
                raise UserError(
                    self.env._("This collection has already been canceled.")
                )
            if not settlement.payment_id:
                raise UserError(
                    self.env._(
                        "Reverse the source bank transaction using the accounting "
                        "workflow."
                    )
                )
            payment = settlement.payment_id
            if payment.move_id.state != "posted":
                raise UserError(
                    self.env._("The payment must be posted before reversal.")
                )
            reversal = payment.move_id.with_context(
                tn_boe_operation=BOE_OPERATION
            )._reverse_moves(
                [
                    {
                        "date": fields.Date.context_today(self),
                        "ref": self.env._(
                            "Cancel bill collection: %(ref)s", ref=settlement.reference
                        ),
                    }
                ],
                cancel=True,
            )
            payment.with_context(tn_boe_operation=BOE_OPERATION).state = "canceled"
            settlement.sudo().write(
                {
                    "canceled": True,
                    "reversal_move_id": reversal.id,
                }
            )
            bill.message_post(
                body=self.env._(
                    "Collection reversed: %(reference)s", reference=settlement.reference
                )
            )
        return True
