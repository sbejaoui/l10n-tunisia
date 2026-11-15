# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        sale_invoices = moves.filtered(
            lambda move: move.state == "draft"
            and move.is_sale_document()
            and move.company_id.chart_template == "tn"
            and move.invoice_line_ids.sale_line_ids
        )
        for move in sale_invoices:
            previous_position = move.fiscal_position_id
            # sales supplies the fiscal position explicitly, bypassing precomputation
            move._compute_fiscal_position_id()
            orders = move.invoice_line_ids.sale_line_ids.order_id
            if move.fiscal_position_id != previous_position or any(
                order.fiscal_position_id != move.fiscal_position_id for order in orders
            ):
                move.action_update_fpos_values()
        return moves
