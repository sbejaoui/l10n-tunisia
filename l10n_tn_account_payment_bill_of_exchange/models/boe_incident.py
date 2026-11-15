# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, fields, models
from odoo.exceptions import UserError


class BoeIncident(models.Model):
    _name = "l10n_tn.boe.incident"
    _description = "Unpaid Bill"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True
    _order = "date desc, id desc"
    _rec_name = "reason"

    bill_id = fields.Many2one(
        "account.payment",
        required=True,
        check_company=True,
        ondelete="restrict",
        index=True,
    )
    invoice_id = fields.Many2one(
        "account.move", required=True, check_company=True, ondelete="restrict"
    )
    company_id = fields.Many2one(related="bill_id.company_id", store=True)
    currency_id = fields.Many2one(related="bill_id.currency_id", store=True)
    partner_id = fields.Many2one(related="bill_id.partner_id", store=True)
    responsible_id = fields.Many2one(related="bill_id.boe_user_id", store=True)
    date = fields.Date(required=True, index=True)
    reason = fields.Char(required=True)
    amount = fields.Monetary(required=True)
    return_move_id = fields.Many2one(
        "account.move", required=True, check_company=True, ondelete="restrict"
    )
    return_line_id = fields.Many2one(
        "account.move.line", required=True, check_company=True, ondelete="restrict"
    )
    invoice_line_id = fields.Many2one(
        "account.move.line", required=True, check_company=True, ondelete="restrict"
    )
    recovery_ids = fields.One2many("l10n_tn.boe.settlement", "incident_id")
    replacement_bill_id = fields.Many2one(
        "account.payment",
        check_company=True,
        ondelete="restrict",
        copy=False,
    )
    replacement_amount = fields.Monetary(copy=False)
    transferred_amount = fields.Monetary(compute="_compute_recovery", store=True)
    state = fields.Selection(
        [("posted", "Posted"), ("reversed", "Reversed")],
        compute="_compute_recovery",
        store=True,
    )
    recovered_amount = fields.Monetary(compute="_compute_recovery", store=True)
    recovery_residual = fields.Monetary(compute="_compute_recovery", store=True)
    pending_amount = fields.Monetary(compute="_compute_recovery", store=True)

    @api.depends(
        "return_move_id.state",
        "return_move_id.reversal_move_ids.state",
        "recovery_ids.state",
        "recovery_ids.amount",
        "amount",
        "replacement_bill_id.state",
        "replacement_amount",
    )
    def _compute_recovery(self):
        for incident in self:
            reversed_move = incident.return_move_id.reversal_move_ids.filtered(
                lambda m: m.state == "posted"
            )
            incident.state = "reversed" if reversed_move else "posted"
            incident.recovered_amount = sum(
                incident.recovery_ids.filtered(lambda s: s.state == "confirmed").mapped(
                    "amount"
                )
            )
            incident.transferred_amount = (
                incident.replacement_amount
                if incident.replacement_bill_id.state
                in ("in_process", "paid", "rejected")
                else 0.0
            )
            incident.pending_amount = sum(
                incident.recovery_ids.filtered(lambda s: s.state == "pending").mapped(
                    "amount"
                )
            )
            incident.recovery_residual = (
                max(
                    0.0,
                    incident.amount
                    - incident.recovered_amount
                    - incident.transferred_amount,
                )
                if incident.state == "posted"
                else 0.0
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_accounting_history(self):
        raise UserError(self.env._("Keep unpaid bill history instead of deleting it."))

    def action_recover(self):
        self.ensure_one()
        action = self.bill_id.action_boe_operation("recover")
        action["context"].update(
            {
                "default_incident_id": self.id,
                "default_amount": self.recovery_residual - self.pending_amount,
            }
        )
        return action
