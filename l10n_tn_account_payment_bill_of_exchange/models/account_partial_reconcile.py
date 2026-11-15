# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, models
from odoo.exceptions import UserError

from .account_payment import BOE_OPERATION


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.constrains("debit_move_id", "credit_move_id", "amount")
    def _check_boe_allocation(self):
        if self.env.context.get("tn_boe_operation") is BOE_OPERATION:
            return
        for partial in self:
            source = partial.credit_move_id
            debit = partial.debit_move_id
            bill = debit.move_id.origin_payment_id
            collection = source.tn_boe_collection_id
            if (
                bill.tn_boe
                and debit.account_id == bill.outstanding_account_id
                and not collection
            ):
                raise UserError(
                    self.env._(
                        "Use the bill collection wizard to record the payment evidence"
                        " before reconciling this effect."
                    )
                )
            if collection:
                target = (
                    collection.incident_id.invoice_line_id
                    if collection.incident_id
                    else collection.bill_id._seek_for_lines()[0]
                )
                payment = collection.payment_id or source.move_id.origin_payment_id
                if (
                    debit not in target
                    or source != collection.source_line_id
                    or (payment and payment.state != "paid" and not payment.is_matched)
                ):
                    raise UserError(
                        self.env._(
                            "Confirm the actual collection and match only its "
                            "designated bill or unpaid invoice."
                        )
                    )
        for line in self.debit_move_id.filtered(
            lambda record: record.move_id.boe_payment_ids
        ):
            incidents = line.move_id.boe_payment_ids.boe_incident_ids.filtered_domain(
                [
                    ("invoice_line_id", "=", line.id),
                    ("state", "=", "posted"),
                ]
            )
            if (
                line.currency_id.compare_amounts(
                    sum(incidents.mapped("recovery_residual")), line.amount_residual
                )
                > 0
            ):
                raise UserError(
                    self.env._(
                        "Allocate the returned principal from its unpaid bill incident"
                        " to keep recovery tracking accurate."
                    )
                )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_boe_invoice_allocation(self):
        internal = self.env.context.get("tn_boe_operation") is BOE_OPERATION
        if not internal:
            for partial in self:
                bill = partial.credit_move_id.move_id.origin_payment_id
                if (
                    bill.tn_boe
                    and partial.debit_move_id.move_id in bill.boe_invoice_ids
                ):
                    raise UserError(
                        self.env._(
                            "Use the unpaid or cancellation action to reopen a bill"
                            " invoice."
                        )
                    )

    def unlink(self):
        internal = self.env.context.get("tn_boe_operation") is BOE_OPERATION
        affected = (self.debit_move_id + self.credit_move_id).move_id.origin_payment_id
        collections = (
            affected.boe_source_settlement_id
            | (self.debit_move_id + self.credit_move_id).tn_boe_collection_id
        ).filtered(lambda s: s.state == "confirmed")
        result = super().unlink()
        if not internal:
            for collection in collections:
                payment = collection.payment_id
                payment.invalidate_recordset(["is_matched"])
                if not payment.is_matched:
                    target = (
                        collection.incident_id.invoice_line_id
                        if collection.incident_id
                        else collection.bill_id._seek_for_lines()[0]
                    )
                    matches = (
                        collection.source_line_id.matched_debit_ids.filtered_domain(
                            [
                                ("debit_move_id", "in", target.ids),
                            ]
                        )
                    )
                    matches.with_context(tn_boe_operation=BOE_OPERATION).unlink()
                    collection.bill_id.message_post(
                        body=self.env._(
                            "Bank matching removed; the collection is pending again."
                        )
                    )
        return result
