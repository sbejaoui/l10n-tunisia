# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, fields, models
from odoo.exceptions import UserError

from .account_payment import BOE_OPERATION


class AccountMove(models.Model):
    _inherit = "account.move"

    boe_payment_ids = fields.Many2many(
        "account.payment",
        "tn_boe_origin_invoice_rel",
        "move_id",
        "payment_id",
        string="Bills of Exchange",
        copy=False,
    )
    tn_boe_incident_id = fields.Many2one(
        "l10n_tn.boe.incident",
        readonly=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )

    def _get_invoice_in_payment_state(self):
        # payment.state depends on invoice.payment_state, use the posted entry
        # and remaining principal to avoid a circular status computation
        if any(
            p.tn_boe and p.move_id.state == "posted" and not p.is_matched
            for p in self.matched_payment_ids
        ):
            return "in_payment"
        return super()._get_invoice_in_payment_state()

    @api.depends(
        "move_type",
        "line_ids.amount_residual",
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
        "boe_payment_ids.boe_reference",
        "boe_payment_ids.boe_maturity_date",
    )
    def _compute_payments_widget_reconciled_info(self):
        result = super()._compute_payments_widget_reconciled_info()
        for move in self:
            if not move.invoice_payments_widget:
                continue
            widget = dict(move.invoice_payments_widget)
            widget["content"] = [dict(item) for item in widget["content"]]
            for item in widget["content"]:
                payment = self.env["account.payment"].browse(
                    item.get("account_payment_id")
                )
                if payment.tn_boe:
                    item.update(
                        boe_reference=payment.boe_reference,
                        boe_maturity_date=fields.Date.to_string(
                            payment.boe_maturity_date
                        ),
                    )
            move.invoice_payments_widget = widget
        return result

    def button_draft(self):
        if self.env.context.get("tn_boe_operation") is not BOE_OPERATION and any(
            m.origin_payment_id.tn_boe or m.origin_payment_id.boe_source_settlement_id
            for m in self
        ):
            raise UserError(
                self.env._("Reverse the bill operation instead of resetting its entry.")
            )
        return super().button_draft()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if self.env.context.get("tn_boe_operation") is not BOE_OPERATION and any(
            move.tn_boe_incident_id
            or move.origin_payment_id.tn_boe
            or move.origin_payment_id.boe_source_settlement_id
            for move in self
        ):
            raise UserError(
                self.env._(
                    "Use the documented bill operation instead of reversing its "
                    "entry directly."
                )
            )
        return super()._reverse_moves(
            default_values_list=default_values_list, cancel=cancel
        )

    def button_cancel(self):
        if self.env.context.get("tn_boe_operation") is not BOE_OPERATION and any(
            m.origin_payment_id.tn_boe or m.origin_payment_id.boe_source_settlement_id
            for m in self
        ):
            raise UserError(
                self.env._("Use the bill cancellation or collection reversal action.")
            )
        return super().button_cancel()
