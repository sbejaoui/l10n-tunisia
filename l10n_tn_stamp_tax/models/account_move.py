from odoo import Command, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _is_stamp_tax_exist(self):
        self.ensure_one()
        stamp_tax_sale = self.env['account.chart.template'].ref("tax_stamp_sale")
        stamp_tax_purchase = self.env['account.chart.template'].ref("tax_stamp_purchase")
        return self.invoice_line_ids.filtered(
            lambda line: (
                stamp_tax_sale in line.tax_ids or stamp_tax_purchase in line.tax_ids
            )
        )
        
    def _is_stamp_tax_applicable(self):
        self.ensure_one()
        return self.company_id.country_id.code == "TN" and self.partner_id.country_id.code == "TN"

    def _post(self, soft=True):
        self.invoice_line_ids.filtered(lambda line: line.is_stamp_tax_line()).unlink()
        self.filtered(
            lambda move: move.state == "draft" and not move._is_stamp_tax_exist() and move._is_stamp_tax_applicable()
        ).add_stamp_tax()
        res = super()._post(soft=soft)
        return res

    def add_stamp_tax(self):
        for move in self:
            move._add_stamp_tax()

    def _add_stamp_tax(self):
        self.ensure_one()
        self.invoice_line_ids = [Command.create(self._prepare_stamp_tax_line_vals())]

    def _prepare_stamp_tax_line_vals(self):
        self.ensure_one()

        if self.is_sale_document(include_receipts=False):
            stamp_tax = self.env['account.chart.template'].ref("tax_stamp_sale")
        elif self.is_purchase_document(include_receipts=False):
            stamp_tax = self.env['account.chart.template'].ref("tax_stamp_purchase")
        else:
            raise ValueError(
                "Stamp not found for this type of document. "
                "Only sale and purchase documents are supported."
            )
        return {
            "quantity": 1.0,
            "price_unit": 0.0,
            "tax_ids": [(6, 0, [stamp_tax.id])],
        }
