# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, fields, models
from odoo.exceptions import UserError

from .account_payment import BOE_OPERATION


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    tn_boe_collection_id = fields.Many2one(
        "l10n_tn.boe.settlement",
        readonly=True,
        copy=False,
        check_company=True,
        ondelete="restrict",
    )

    @api.model
    def _prepare_reconciliation_plan(
        self, plan, amls_values_map, shadowed_aml_values=None
    ):
        allocation = self.env.context.get("tn_boe_allocation")
        if allocation and self.env.context.get("tn_boe_operation") is BOE_OPERATION:
            line_id, amount = allocation
            amls_values_map = dict(amls_values_map)
            for line, values in amls_values_map.items():
                if line.id != line_id:
                    continue
                if (
                    line.currency_id != line.company_currency_id
                    or amount <= 0
                    or line.currency_id.compare_amounts(
                        amount, abs(values["amount_residual"])
                    )
                    > 0
                ):
                    raise UserError(
                        self.env._(
                            "The replacement allocation exceeds the available TND"
                            " principal."
                        )
                    )
                # cap the virtual credit, keep the real invoice residual unchanged
                signed = amount if values["amount_residual"] > 0 else -amount
                amls_values_map[line] = {
                    **values,
                    "amount_residual": signed,
                    "amount_residual_currency": signed,
                }
        return super()._prepare_reconciliation_plan(
            plan,
            amls_values_map,
            shadowed_aml_values=shadowed_aml_values,
        )

    def write(self, vals):
        if (
            "tn_boe_collection_id" in vals
            and self.env.context.get("tn_boe_operation") is not BOE_OPERATION
        ):
            raise UserError(
                self.env._("Collection allocations are managed by the bill workflow.")
            )
        if self.env.context.get("tn_boe_operation") is not BOE_OPERATION and {
            "account_id",
            "partner_id",
            "balance",
            "debit",
            "credit",
            "amount_currency",
            "currency_id",
            "move_id",
            "date_maturity",
        }.intersection(vals):
            protected = self.filtered(
                lambda line: (
                    line.move_id.state == "posted"
                    and (
                        line.move_id.origin_payment_id.tn_boe
                        or line.move_id.origin_payment_id.boe_source_settlement_id
                        or line.move_id.tn_boe_incident_id
                    )
                )
            )
            if protected:
                raise UserError(
                    self.env._(
                        "Use the bill workflow to correct its posted accounting lines."
                    )
                )
        return super().write(vals)
