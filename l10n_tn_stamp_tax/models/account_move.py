from odoo import Command, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _is_stamp_tax_exist(self):
        self.ensure_one()
        stamp_tax_sale = self.env.ref("l10n_tn_stamp_tax.tax_stamp_sale")
        stamp_tax_purchase = self.env.ref("l10n_tn_stamp_tax.tax_stamp_purchase")
        return self.invoice_line_ids.filtered(
            lambda line: (
                stamp_tax_sale in line.tax_ids or stamp_tax_purchase in line.tax_ids
            )
        )

    def _post(self, soft=True):
        self.filtered(
            lambda move: move.state == "draft" and not move._is_stamp_tax_exist()
        ).add_stamp_tax()
        res = super()._post(soft=soft)
        return res

    def add_stamp_tax(self):
        for move in self:
            move._add_stamp_tax()

    def _add_stamp_tax(self):
        self.ensure_one()
        self.invoice_line_ids = [(Command.create(self._prepare_stamp_tax_line_vals()))]

    def _prepare_stamp_tax_line_vals(self):
        self.ensure_one()

        if self.is_sale_document(include_receipts=False):
            stamp_tax = self.env.ref("l10n_tn_stamp_tax.tax_stamp_sale")
        elif self.is_purchase_document(include_receipts=False):
            stamp_tax = self.env.ref("l10n_tn_stamp_tax.tax_stamp_purchase")
        else:
            raise ValueError(
                "Stamp not found for this type of document. Only sale and purchase documents are supported."
            )
        return {
            "name": stamp_tax.name,
            "quantity": 1.0,
            "price_unit": stamp_tax.amount,
            "tax_ids": [(6, 0, [stamp_tax.id])],
        }
