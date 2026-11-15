# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = "account.payment.method"

    @api.model
    def _get_payment_method_information(self):
        result = super()._get_payment_method_information()
        result["tn_bill_of_exchange"] = {
            "mode": "unique",
            "type": ("bank",),
            "country_id": self.env.ref("base.tn").id,
            "currency_ids": self.env.ref("base.TND").ids,
        }
        return result
