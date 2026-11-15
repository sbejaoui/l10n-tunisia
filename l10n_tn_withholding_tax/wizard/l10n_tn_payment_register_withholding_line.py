# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class L10nTnPaymentRegisterWithholdingLine(models.TransientModel):
    _name = "l10n_tn.payment.register.withholding.line"
    _description = "Invoice Payment and Withholding Allocation"
    _order = "id"

    wizard_id = fields.Many2one(
        "account.payment.register",
        required=True,
        ondelete="cascade",
    )
    invoice_id = fields.Many2one("account.move", required=True, readonly=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id")
    invoice_balance = fields.Monetary(string="Remaining Balance", readonly=True)
    available_withholding_journal_ids = fields.Many2many(
        "account.journal",
        compute="_compute_available_withholding_journal_ids",
    )
    withholding_journal_ids = fields.Many2many(
        "account.journal",
        "account_payment_withholding_allocation_journal_rel",
        "allocation_id",
        "journal_id",
        string="Withholding Taxes",
        domain="[('id', 'in', available_withholding_journal_ids)]",
    )
    withholding_amount = fields.Monetary(compute="_compute_withholding_amount")
    cash_amount = fields.Monetary(
        string="Cash Allocation",
        compute="_compute_cash_amount",
        store=True,
        readonly=False,
    )

    @api.depends(
        "invoice_id",
        "invoice_id.l10n_tn_is_domestic_transaction",
        "invoice_id.matched_payment_ids.state",
    )
    def _compute_available_withholding_journal_ids(self):
        rules = self.env["l10n.tn.withholding.rule"]
        for line in self:
            line.available_withholding_journal_ids = rules._get_applicable_rules(
                line.invoice_id
            ).withholding_journal_id

    def _get_withholding_amounts(self):
        self.ensure_one()
        return [
            (
                journal,
                self.currency_id.round(
                    self.invoice_id.amount_total * journal.withholding_tax_rate
                ),
            )
            for journal in self.withholding_journal_ids
        ]

    @api.depends(
        "withholding_journal_ids.withholding_tax_rate",
        "invoice_id.amount_total",
        "currency_id",
    )
    def _compute_withholding_amount(self):
        for line in self:
            line.withholding_amount = sum(
                amount for _journal, amount in line._get_withholding_amounts()
            )

    @api.depends("invoice_balance", "withholding_amount")
    def _compute_cash_amount(self):
        for line in self:
            line.cash_amount = max(line.invoice_balance - line.withholding_amount, 0)
