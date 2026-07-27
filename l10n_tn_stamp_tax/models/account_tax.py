# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import ormcache


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_tn_is_stamp_tax = fields.Boolean(string="Is Stamp Tax")

    @api.model
    @ormcache("tax_type", "company_id")
    def _get_stamp_tax(self, tax_type, company_id):
        stamp_tax = self.env["account.tax"].search(
            [
                ("l10n_tn_is_stamp_tax", "=", True),
                ("type_tax_use", "=", tax_type),
                ("company_id", "=", company_id),
            ],
            limit=1,
        )
        if not stamp_tax:
            raise ValidationError(
                self.env._(
                    "Stamp tax not found for this type of document. "
                    "Please ensure that a stamp tax is configured for the company."
                )
            )
        return stamp_tax

    @api.model_create_multi
    def create(self, vals_list):
        taxes = super().create(vals_list)
        self.env._get_stamp_tax.clear_cache()
        return taxes

    def write(self, vals):
        res = super().write(vals)
        self.env._get_stamp_tax.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env._get_stamp_tax.clear_cache()
        return res
