from odoo import Command, models
from odoo.exceptions import ValidationError
from odoo.tools import ormcache


class AccountMove(models.Model):
    _inherit = "account.move"

    @ormcache()
    def _get_stamp_tax(self):
        self.ensure_one()
        stamp_tax = self.env["account.tax"].search(
            [
                ("l10n_tn_is_stamp_tax", "=", True),
                (
                    "type_tax_use",
                    "=",
                    "sale" if self.is_sale_document() else "purchase",
                ),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not stamp_tax:
            raise ValidationError(
                "Stamp tax not found for this type of document. "
                "Please ensure that a stamp tax is configured for the company."
            )
        return stamp_tax

    def _is_stamp_tax_exist(self):
        self.ensure_one()
        return bool(self.invoice_line_ids.filtered("l10n_tn_is_stamp_tax"))

    def _is_stamp_tax_applicable(self):
        self.ensure_one()
        return (
            self.company_id.country_id.code == "TN"
            and self.partner_id.country_id.code == "TN"
        )

    def _clean_stamp_tax_lines(self):
        for move in self:
            move.invoice_line_ids.filtered("l10n_tn_is_stamp_tax").unlink()
            stamp_tax = move._get_stamp_tax()
            move.invoice_line_ids.write({"tax_ids": [Command.unlink(stamp_tax.id)]})

    def _post(self, soft=True):
        self._clean_stamp_tax_lines()
        self.filtered(
            lambda move: (
                move.state == "draft"
                and not move._is_stamp_tax_exist()
                and move._is_stamp_tax_applicable()
            )
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
        stamp_tax = self._get_stamp_tax()
        return {
            "quantity": 1.0,
            "price_unit": 0.0,
            "l10n_tn_is_stamp_tax": True,
            "tax_ids": [(6, 0, [stamp_tax.id])],
        }
