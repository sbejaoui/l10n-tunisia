# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
import json

from odoo import api, fields, models
from odoo.exceptions import AccessError


class SpreadsheetDashboard(models.Model):
    _inherit = "spreadsheet.dashboard"

    tn_boe_dashboard = fields.Boolean(string="Bills Follow-up Dashboard")

    def _get_serialized_readonly_dashboard(self):
        result = super()._get_serialized_readonly_dashboard()
        if self.tn_boe_dashboard:
            data = json.loads(result)
            timestamp = fields.Datetime.context_timestamp(
                self, fields.Datetime.now()
            ).strftime("%d/%m/%Y %H:%M:%S")
            for sheet in data["snapshot"]["sheets"]:
                sheet["cells"]["B2"] = timestamp
            return json.dumps(data)
        return result


class SpreadsheetDashboardShare(models.Model):
    _inherit = "spreadsheet.dashboard.share"

    @api.constrains("dashboard_id")
    def _check_boe_public_share(self):
        if self.dashboard_id.filtered("tn_boe_dashboard"):
            raise AccessError(
                self.env._(
                    "Use the authenticated bill dashboard. Public snapshots cannot "
                    "preserve each viewer's accounting access rights."
                )
            )
