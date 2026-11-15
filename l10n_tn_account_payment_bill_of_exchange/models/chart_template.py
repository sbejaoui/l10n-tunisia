# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("tn", "account.journal")
    def _get_tn_boe_journal(self):
        return {
            "tn_boe": {
                "name": self.env._("Customer Bills of Exchange"),
                "code": "TRT",
                "type": "bank",
                "tn_boe_journal": True,
                "show_on_dashboard": False,
                # false is applied at creation; relational commands are deferred
                # until after method lines load and would detach the bill method
                "inbound_payment_method_line_ids": False,
                "outbound_payment_method_line_ids": False,
            },
        }

    @template("tn", "account.payment.method.line")
    def _get_tn_boe_method_line(self):
        method = self.ref("tn_boe_inbound", raise_if_not_found=False)
        if method and method.journal_id:
            return {}
        if method:
            # restore detached lines without resetting their configured account
            return {"tn_boe_inbound": {"journal_id": "tn_boe"}}
        payment_method_id = (
            "l10n_tn_account_payment_bill_of_exchange.payment_method_boe"
        )
        return {
            "tn_boe_inbound": {
                "journal_id": "tn_boe",
                "payment_method_id": payment_method_id,
                "payment_account_id": "l10n_tn_413",
            },
        }
