# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    boe_reference = fields.Char()
    boe_issue_date = fields.Date(default=fields.Date.context_today)
    boe_maturity_date = fields.Date()
    boe_received_date = fields.Date(default=fields.Date.context_today)
    boe_acceptance_date = fields.Date(default=fields.Date.context_today)
    boe_signed_document = fields.Binary()
    boe_signed_filename = fields.Char()
    boe_user_id = fields.Many2one("res.users", default=lambda self: self.env.user)

    @api.onchange("payment_method_line_id")
    def _onchange_boe_group_payment(self):
        if self.payment_method_code == "tn_bill_of_exchange" and self.can_edit_wizard:
            self.group_payment = True

    def _boe_payment_values(self):
        return {
            "boe_reference": self.boe_reference,
            "boe_issue_date": self.boe_issue_date,
            "boe_maturity_date": self.boe_maturity_date,
            "boe_received_date": self.boe_received_date,
            "boe_acceptance": "accepted",
            "boe_acceptance_date": self.boe_acceptance_date,
            "boe_signed_document": self.boe_signed_document,
            "boe_signed_filename": self.boe_signed_filename,
            "boe_user_id": self.boe_user_id.id,
            "boe_invoice_ids": [Command.set(self.line_ids.move_id.ids)],
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        result = super()._create_payment_vals_from_wizard(batch_result)
        if self.payment_method_code == "tn_bill_of_exchange":
            result.update(self._boe_payment_values())
            if result.pop("write_off_line_vals", None):
                raise UserError(self.env._("Bill receipts do not support write-offs."))
        return result

    def _create_payment_vals_from_batch(self, batch_result):
        result = super()._create_payment_vals_from_batch(batch_result)
        if self.payment_method_code == "tn_bill_of_exchange":
            result.update(self._boe_payment_values())
            if result.pop("write_off_line_vals", None):
                raise UserError(self.env._("Bill receipts do not support write-offs."))
        return result

    def _create_payments(self):
        self.ensure_one()
        if self.payment_method_code != "tn_bill_of_exchange":
            return super()._create_payments()
        invoices = self.line_ids.move_id
        if (
            not invoices
            or len(invoices.commercial_partner_id) != 1
            or len(invoices.company_id) != 1
            or len(self.batches) != 1
            or len(self.line_ids.account_id) != 1
            or any(
                i.move_type != "out_invoice" or i.state != "posted" for i in invoices
            )
            or (len(invoices) > 1 and not self.group_payment)
            or self.payment_difference_handling != "open"
            or self.early_payment_discount_mode
        ):
            raise UserError(
                self.env._(
                    "Select posted customer invoices for one customer, company and "
                    "receivable account, group the payment and keep differences open. "
                    "Early discounts are not supported."
                )
            )
        self.lock_for_update()
        invoices.lock_for_update()
        self.line_ids.invalidate_recordset()
        return super()._create_payments()

    def _reconcile_payments(self, to_process, edit_mode=False):
        regular = [values for values in to_process if not values["payment"].tn_boe]
        return super()._reconcile_payments(regular, edit_mode=edit_mode)
