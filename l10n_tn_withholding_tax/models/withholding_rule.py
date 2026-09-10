# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.tools.misc import formatLang


class WithholdingRule(models.Model):
    _name = "l10n.tn.withholding.rule"

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Article",
    )
    description = fields.Text()
    amount = fields.Float()
    withholding_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Withholding Tax Journal",
    )

    def _get_applicable_rules(self, invoices):
        applicable_rules = self.env["l10n.tn.withholding.rule"]
        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                rule = self.search([("product_id", "=", line.product_id.id)], limit=1)
                if (
                    rule
                    and not invoice.is_withholding_tax_rule_applied(rule)
                    and invoice.amount_total >= rule.amount
                ):
                    applicable_rules |= rule
        return applicable_rules

    def _get_withholding_alert_message(self, amount, currency):
        self.ensure_one()
        formatted_price = formatLang(self.env, amount, currency_obj=currency)
        return (
            f"- {self.product_id.name}:"
            + f" {self.withholding_journal_id.name}"
            + f" ({formatted_price})\n"
        )

    def _get_withholding_amount(self, invoices):
        self.ensure_one()
        total = sum(invoice.amount_total for invoice in invoices)
        return total * self.withholding_journal_id.withholding_tax_rate
