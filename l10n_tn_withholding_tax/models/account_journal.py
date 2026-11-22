# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_withholding_tax_journal = fields.Boolean(
        string="Journal includes Withholding Tax",
    )
    withholding_direction = fields.Selection(
        selection=[
            ("inbound", "Customer withholding (received)"),
            ("outbound", "Supplier withholding (deducted)"),
        ],
        help="Incoming for customer withholding; outgoing for supplier withholding.",
    )
    withholding_tax_rate = fields.Float(string="Rate")
    withholding_payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        compute="_compute_withholding_payment_method_line_id",
    )
    withholding_has_manual_method = fields.Boolean(
        compute="_compute_withholding_payment_method_line_id",
    )
    withholding_account_id = fields.Many2one(
        string="Withholding Account",
        related="withholding_payment_method_line_id.payment_account_id",
        depends=[
            "withholding_payment_method_line_id",
            "inbound_payment_method_line_ids.payment_account_id",
            "outbound_payment_method_line_ids.payment_account_id",
        ],
        readonly=False,
        check_company=True,
        help="Tax account used for withholding payments in this journal.",
    )

    @api.depends(
        "is_withholding_tax_journal",
        "withholding_direction",
        "inbound_payment_method_line_ids.payment_method_id.code",
        "outbound_payment_method_line_ids.payment_method_id.code",
    )
    def _compute_withholding_payment_method_line_id(self):
        for journal in self:
            methods = self.env["account.payment.method.line"]
            if journal.is_withholding_tax_journal and journal.withholding_direction:
                methods = (
                    journal.inbound_payment_method_line_ids
                    if journal.withholding_direction == "inbound"
                    else journal.outbound_payment_method_line_ids
                )
            manual_method = methods.filtered(
                lambda method: method.payment_method_id.code == "manual"
            )[:1]
            journal.withholding_payment_method_line_id = manual_method
            # new method lines have no persistent id for form modifiers
            journal.withholding_has_manual_method = bool(manual_method)

    @api.constrains("is_withholding_tax_journal", "withholding_direction")
    def _check_withholding_direction(self):
        for journal in self:
            if journal.is_withholding_tax_journal and not journal.withholding_direction:
                raise ValidationError(
                    self.env._("A withholding tax journal must have a direction.")
                )

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
        "withholding_direction",
        "company_id",
        "default_account_id",
        "inbound_payment_method_line_ids",
        "outbound_payment_method_line_ids",
    )
    def _check_withholding_method_accounts(self):
        for journal in self.filtered("is_withholding_tax_journal"):
            methods = journal._get_available_payment_method_lines(
                journal.withholding_direction
            )
            for method in methods.filtered("payment_account_id"):
                journal._check_withholding_account(method.payment_account_id)
