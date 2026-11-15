# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def _prepare_reconciliation_plan(
        self, plan, amls_values_map, shadowed_aml_values=None
    ):
        allocation = self.env.context.get("l10n_tn_payment_allocation")
        if allocation:
            payment_line_id, amount = allocation
            # cap only the virtual payment balance, real invoice residuals stay intact
            amls_values_map = dict(amls_values_map)
            for aml, values in amls_values_map.items():
                if aml.id != payment_line_id:
                    continue
                if aml.currency_id != aml.company_currency_id:
                    raise UserError(
                        self.env._("Invoice allocations require the company currency.")
                    )
                if (
                    not aml.move_id.origin_payment_id
                    or aml.company_currency_id.compare_amounts(amount, 0) <= 0
                    or aml.company_currency_id.compare_amounts(
                        amount, abs(values["amount_residual"])
                    )
                    > 0
                ):
                    raise UserError(
                        self.env._(
                            "The requested payment allocation is no longer valid."
                        )
                    )
                sign = 1 if values["amount_residual"] > 0 else -1
                limit = min(abs(values["amount_residual"]), amount)
                amls_values_map[aml] = dict(
                    values,
                    amount_residual=sign * limit,
                    amount_residual_currency=sign * limit,
                )
        return super()._prepare_reconciliation_plan(
            plan, amls_values_map, shadowed_aml_values=shadowed_aml_values
        )
