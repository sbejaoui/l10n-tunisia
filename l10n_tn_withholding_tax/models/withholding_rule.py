# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
