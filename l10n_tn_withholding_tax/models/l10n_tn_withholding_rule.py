# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang


class WithholdingRule(models.Model):
    _name = "l10n.tn.withholding.rule"
    _description = "Tunisian Withholding Tax Rule"

    product_id = fields.Many2many(
        comodel_name="product.product",
        string="Article",
        help="Leave empty to apply the rule to any invoice meeting the minimum amount.",
    )
    description = fields.Text()
    move_type = fields.Selection(
        [("out_invoice", "Customer Invoice"), ("in_invoice", "Vendor Bill")],
        string="Document Type",
        help="Leave empty to apply to both customer invoices and vendor bills.",
    )
    amount = fields.Float()
    withholding_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Withholding Tax Journal",
        domain=[("is_withholding_tax_journal", "=", True)],
    )

    def _get_applicable_rules(self, invoices):
        applicable_rules = self.env["l10n.tn.withholding.rule"]
        for invoice in invoices:
            if invoice.move_type not in ("out_invoice", "in_invoice") or not (
                invoice._is_withholding_tax_applicable()
            ):
                continue
            journals = self.env["account.journal"].search(
                [
                    ("company_id", "=", invoice.company_id.id),
                    ("is_withholding_tax_journal", "=", True),
                ]
            )
            rule_domain = [
                ("withholding_journal_id", "in", journals.ids),
                ("move_type", "in", [False, invoice.move_type]),
            ]
            amount_rules = self.search(
                rule_domain
                + [("product_id", "=", False), ("amount", "<=", invoice.amount_total)]
            )
            applicable_rules |= amount_rules.filtered(
                lambda rule, bill=invoice: (
                    not bill.is_withholding_tax_rule_applied(rule)
                )
            )
            for line in invoice.invoice_line_ids:
                if not line.product_id:
                    continue
                rule = self.search(
                    rule_domain
                    + [
                        ("product_id", "=", line.product_id.id),
                        ("amount", "<=", invoice.amount_total),
                    ],
                    order="amount desc, id",
                    limit=1,
                )
                if rule and not invoice.is_withholding_tax_rule_applied(rule):
                    applicable_rules |= rule
        return applicable_rules

    def _get_withholding_alert_message(self, amount, currency, invoices):
        self.ensure_one()
        formatted_price = formatLang(self.env, amount, currency_obj=currency)
        matching_products = self.product_id & invoices.invoice_line_ids.product_id
        product_names = ", ".join(matching_products.mapped("display_name"))
        if not self.product_id:
            product_names = self.description or self.env._("All invoices")
        return (
            f"- {product_names}:"
            + f" {self.withholding_journal_id.name}"
            + f" ({formatted_price})\n"
        )

    def _get_withholding_amount(self, invoices):
        self.ensure_one()
        total = sum(invoice.amount_total for invoice in invoices)
        return total * self.withholding_journal_id.withholding_tax_rate

    def _get_net_amount(self, invoices):
        self.ensure_one()
        total = sum(invoice.amount_total for invoice in invoices)
        return total - self._get_withholding_amount(invoices)

    @api.constrains("amount")
    def _check_amount_is_not_negative(self):
        for rule in self:
            if rule.amount < 0:
                raise ValidationError(
                    self.env._("The minimum invoice amount cannot be negative.")
                )
