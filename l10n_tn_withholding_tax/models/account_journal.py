# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_withholding_tax_journal = fields.Boolean(
        string="Journal includes Withholding Tax",
    )
    withholding_tax_rate = fields.Float(string="Rate")

    @api.constrains("is_withholding_tax_journal", "type", "withholding_tax_rate")
    def _check_withholding_configuration(self):
        for journal in self.filtered("is_withholding_tax_journal"):
            if journal.type != "bank":
                raise ValidationError(
                    self.env._("A withholding tax journal must be a bank journal.")
                )
            if not 0 < journal.withholding_tax_rate <= 1:
                raise ValidationError(
                    self.env._(
                        "The withholding rate must be greater than 0 "
                        "and at most 1 (1 = 100%)."
                    )
                )

    def _check_withholding_account(self, account):
        self.ensure_one()
        if (
            not account
            or not account.active
            or account.account_type not in ("asset_current", "liability_current")
            or account
            in (self.default_account_id | self.company_id.transfer_account_id)
            or not account.filtered_domain(
                account._check_company_domain(self.company_id)
            )
        ):
            raise ValidationError(
                self.env._(
                    "Configure an active fiscal account for journal %(journal)s "
                    "of type Current Assets or Current Liabilities. "
                    "It must belong to the journal company and differ "
                    "from the bank and transfer accounts.",
                    journal=self.display_name,
                )
            )

    @api.constrains(
        "is_withholding_tax_journal",
        "company_id",
        "default_account_id",
        "inbound_payment_method_line_ids",
        "outbound_payment_method_line_ids",
    )
    def _check_withholding_method_accounts(self):
        for journal in self.filtered("is_withholding_tax_journal"):
            methods = (
                journal.inbound_payment_method_line_ids
                | journal.outbound_payment_method_line_ids
            )
            for method in methods.filtered("payment_account_id"):
                journal._check_withholding_account(method.payment_account_id)
