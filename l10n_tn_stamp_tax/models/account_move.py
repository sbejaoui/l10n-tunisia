# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _is_stamp_tax_applicable(self):
        self.ensure_one()
        return (
            self.company_id.country_id.code == "TN"
            and self.partner_id.country_id.code == "TN"
        )

    def _clean_stamp_tax_lines(self):
        for move in self:
            move.invoice_line_ids.filtered("l10n_tn_is_stamp_tax").unlink()
            tax_type = "sale" if move.is_sale_document() else "purchase"
            stamp_tax = self.env["account.tax"]._get_stamp_tax(
                tax_type, move.company_id.id
            )
            move.invoice_line_ids.write({"tax_ids": [Command.unlink(stamp_tax.id)]})

    def _post(self, soft=True):
        self._clean_stamp_tax_lines()
        self.filtered(
            lambda move: (move.state == "draft" and move._is_stamp_tax_applicable())
        )._add_stamp_tax()
        res = super()._post(soft=soft)
        return res

    def _add_stamp_tax(self):
        for move in self:
            move.invoice_line_ids = [
                Command.create(move._prepare_stamp_tax_line_vals())
            ]

    def _prepare_stamp_tax_line_vals(self):
        self.ensure_one()
        tax_type = "sale" if self.is_sale_document() else "purchase"
        stamp_tax = self.env["account.tax"]._get_stamp_tax(tax_type, self.company_id.id)
        return {
            "quantity": 1.0,
            "price_unit": 0.0,
            "l10n_tn_is_stamp_tax": True,
            "tax_ids": [(6, 0, [stamp_tax.id])],
        }
