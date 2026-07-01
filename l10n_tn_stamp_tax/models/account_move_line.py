from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def is_stamp_tax_line(self):
        self.ensure_one()
        stamp_tax_sale = self.env.ref("l10n_tn_stamp_tax.tax_stamp_sale")
        stamp_tax_purchase = self.env.ref("l10n_tn_stamp_tax.tax_stamp_purchase")
        return stamp_tax_sale in self.tax_ids or stamp_tax_purchase in self.tax_ids
