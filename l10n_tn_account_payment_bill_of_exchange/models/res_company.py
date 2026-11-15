# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    tn_boe_reminder_days = fields.Integer(default=7)
    tn_boe_escalation_days = fields.Integer(default=7)
    tn_boe_manager_id = fields.Many2one(
        "res.users", string="Bills Follow-up Manager", check_company=True
    )

    @api.constrains("tn_boe_reminder_days", "tn_boe_escalation_days")
    def _check_boe_reminder_days(self):
        if any(
            company.tn_boe_reminder_days < 0 or company.tn_boe_escalation_days < 0
            for company in self
        ):
            raise ValidationError(self.env._("Follow-up delays cannot be negative."))

    def action_setup_tn_boe(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(
                self.env._("Only accounting managers can configure bills.")
            )
        self.check_access("write")
        for company in self:
            if company not in self.env.companies or company.chart_template != "tn":
                raise UserError(
                    self.env._("Select an authorized Tunisian chart company.")
                )
            chart = self.env["account.chart.template"].with_company(company)
            journal = chart.ref("tn_boe", raise_if_not_found=False)
            method = chart.ref("tn_boe_inbound", raise_if_not_found=False)
            data = {}
            if not journal:
                data["account.journal"] = chart._get_tn_boe_journal()
            if not method or not method.journal_id:
                data["account.payment.method.line"] = chart._get_tn_boe_method_line()
            # load missing bill records or restore a detached method line
            chart._load_data(data)
        return True
