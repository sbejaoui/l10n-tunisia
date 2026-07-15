from odoo import api, fields, models
from odoo.tools import ormcache
from odoo.exceptions import ValidationError


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
                "Stamp tax not found for this type of document. "
                "Please ensure that a stamp tax is configured for the company."
            )
        return stamp_tax

    @api.model_create_multi
    def create(self, vals_list):
        taxes = super().create(vals_list)
        self.env.registry.clear_cache()
        return taxes

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res
