# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date, formatLang


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_tn_tax_exemption_id = fields.Many2one(
        "l10n_tn.tax_exemption",
        string="Tax Exemption",
        ondelete="restrict",
        compute="_compute_l10n_tn_tax_exemption_id",
        store=True,
        readonly=False,
        precompute=True,
    )

    l10n_tn_endorsed_purchase_order = fields.Char(string="Endorsed Purchase Order")
    l10n_tn_endorsed_purchase_order_date = fields.Date(
        string="Endorsed Purchase Order Date"
    )
    l10n_tn_endorsed_purchase_order_file = fields.Binary(
        string="Endorsed Purchase Order File",
        attachment=True,
        copy=False,
    )
    l10n_tn_endorsed_purchase_order_filename = fields.Char(copy=False)
    l10n_tn_tax_exemption_warning = fields.Text(
        string="Tax Exemption Notice",
        compute="_compute_l10n_tn_tax_exemption_warnings",
    )
    l10n_tn_tax_exemption_missing_warning = fields.Text(
        string="Missing Tax Exemption Information",
        compute="_compute_l10n_tn_tax_exemption_warnings",
    )
    l10n_tn_tax_exemption_reminder_warning = fields.Text(
        string="Previous Tax Exemption Reminder",
        compute="_compute_l10n_tn_tax_exemption_reminder_warning",
    )
    l10n_tn_is_exemption_fiscal_position = fields.Boolean(
        compute="_compute_l10n_tn_is_exemption_fiscal_position",
    )
    l10n_tn_suspended_vat_amount = fields.Monetary(
        string="Indicative Suspended VAT",
        compute="_compute_l10n_tn_suspended_vat_amount",
    )

    @api.depends(
        "move_type",
        "l10n_tn_tax_exemption_id",
        "l10n_tn_tax_exemption_id.fiscal_position_id.tax_ids",
        "currency_id.rounding",
        "company_id.tax_calculation_rounding_method",
        "invoice_line_ids.display_type",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.quantity",
        "invoice_line_ids.tax_ids.amount",
        "invoice_line_ids.tax_ids.amount_type",
        "invoice_line_ids.tax_ids.original_tax_ids",
        "invoice_line_ids.product_id.taxes_id.amount",
        "invoice_line_ids.product_id.taxes_id.amount_type",
        "invoice_line_ids.account_id.tax_ids.amount",
        "invoice_line_ids.account_id.tax_ids.amount_type",
    )
    def _compute_l10n_tn_suspended_vat_amount(self):
        account_tax = self.env["account.tax"]
        for move in self:
            move.l10n_tn_suspended_vat_amount = 0
            if not move.is_sale_document() or not move.l10n_tn_tax_exemption_id:
                continue
            base_lines = []
            for line in move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            ):
                original_taxes = line.product_id.taxes_id._filter_taxes_by_company(
                    move.company_id
                ) or line.account_id.tax_ids.filtered(
                    lambda tax: tax.type_tax_use == "sale"
                )._filter_taxes_by_company(move.company_id)
                exempt_taxes = (
                    line.tax_ids
                    & move.l10n_tn_tax_exemption_id.fiscal_position_id.tax_ids
                ).filtered(
                    lambda tax: tax.amount_type in ("percent", "division")
                    and tax.amount == 0
                )
                suspended_taxes = original_taxes & exempt_taxes.original_tax_ids
                if suspended_taxes:
                    base_lines.append(
                        account_tax._prepare_base_line_for_taxes_computation(
                            line,
                            tax_ids=suspended_taxes,
                            price_unit=(
                                line.price_subtotal / line.quantity
                                if line.quantity
                                else 0
                            ),
                            quantity=line.quantity,
                            discount=0,
                            special_mode="total_excluded",
                            extra_tax_data={},
                            rate=line.currency_rate or 1,
                        )
                    )
            account_tax._add_tax_details_in_base_lines(base_lines, move.company_id)
            account_tax._round_base_lines_tax_details(base_lines, move.company_id)
            move.l10n_tn_suspended_vat_amount = move.currency_id.round(
                sum(
                    tax_data["tax_amount_currency"]
                    for base_line in base_lines
                    for tax_data in base_line["tax_details"]["taxes_data"]
                )
            )

    @api.depends("fiscal_position_id", "company_id")
    def _compute_l10n_tn_is_exemption_fiscal_position(self):
        for move in self:
            exemption_position = (
                self.env["account.chart.template"]
                .with_company(move.company_id)
                .ref("fiscal_position_template_exo", raise_if_not_found=False)
            )
            move.l10n_tn_is_exemption_fiscal_position = bool(
                exemption_position and move.fiscal_position_id == exemption_position
            )

    @api.depends(
        "state",
        "move_type",
        "invoice_date",
        "partner_id",
        "partner_id.commercial_partner_id.l10n_tn_tax_exemption_ids.date_end",
        "partner_id.commercial_partner_id.l10n_tn_tax_exemption_ids.name",
        "company_id.l10n_tn_tax_exemption_reminder_months",
        "l10n_tn_tax_exemption_id.date_start",
        "l10n_tn_tax_exemption_id.date_end",
        "l10n_tn_is_domestic_transaction",
    )
    @api.depends_context("lang")
    def _compute_l10n_tn_tax_exemption_reminder_warning(self):
        for move in self:
            move.l10n_tn_tax_exemption_reminder_warning = False
            months = move.company_id.l10n_tn_tax_exemption_reminder_months
            if (
                move.state != "draft"
                or not move.partner_id
                or not move._is_tax_exemption_applicable()
                or months <= 0
            ):
                continue
            date = move.invoice_date or fields.Date.context_today(move)
            selected = move.l10n_tn_tax_exemption_id
            if (
                selected.date_start
                and selected.date_end
                and selected.date_start <= date <= selected.date_end
            ):
                continue
            expired = self.env["l10n_tn.tax_exemption"].search(
                [
                    ("partner_id", "=", move.partner_id.commercial_partner_id.id),
                    ("date_end", "<", date),
                    ("date_end", ">=", fields.Date.subtract(date, months=months)),
                ],
                order="date_end desc, id desc",
                limit=1,
            )
            if expired:
                move.l10n_tn_tax_exemption_reminder_warning = self.env._(
                    "This customer was previously tax exempt. Certificate "
                    "%(certificate)s expired on %(date)s. Please check whether "
                    "the customer is still exempt and request an updated certificate.",
                    certificate=expired.display_name,
                    date=format_date(self.env, expired.date_end),
                )

    @api.depends(
        "move_type",
        "state",
        "l10n_tn_tax_exemption_id.name",
        "l10n_tn_tax_exemption_id.date_issue",
        "l10n_tn_tax_exemption_id.date_end",
        "l10n_tn_suspended_vat_amount",
        "currency_id",
        "fiscal_position_id",
        "l10n_tn_endorsed_purchase_order",
        "l10n_tn_endorsed_purchase_order_date",
        "l10n_tn_endorsed_purchase_order_file",
    )
    @api.depends_context("lang")
    def _compute_l10n_tn_tax_exemption_warnings(self):
        for move in self:
            move.l10n_tn_tax_exemption_warning = False
            move.l10n_tn_tax_exemption_missing_warning = False
            exemption = move.l10n_tn_tax_exemption_id
            if not exemption or not move.is_sale_document():
                continue
            not_provided = self.env._("Not provided")
            message = self.env._(
                "Indicative suspended VAT amount: %(amount)s %(currency)s",
                amount=formatLang(
                    self.env,
                    move.l10n_tn_suspended_vat_amount,
                    digits=move.currency_id.decimal_places,
                ),
                currency=move.currency_id.name,
            )
            if (
                move.l10n_tn_endorsed_purchase_order
                and move.l10n_tn_endorsed_purchase_order_date
            ):
                message += "\n" + self.env._(
                    "Endorsed purchase order number: %(order)s",
                    order=move.l10n_tn_endorsed_purchase_order,
                )
            message += "\n" + self.env._(
                "Tax exemption certificate No.: %(certificate)s\n"
                "Exemption expiry date: %(expiry_date)s",
                certificate=exemption.name or not_provided,
                expiry_date=(
                    format_date(self.env, exemption.date_end)
                    if exemption.date_end
                    else not_provided
                ),
            )
            move.l10n_tn_tax_exemption_warning = message
            if move.state != "draft":
                continue
            missing = [
                label
                for value, label in (
                    (exemption.name, self.env._("Certificate Number")),
                    (exemption.date_issue, self.env._("Certificate Issue Date")),
                    (exemption.date_end, self.env._("Certificate Expiry Date")),
                    (move.fiscal_position_id, self.env._("Fiscal Position")),
                    (
                        move.l10n_tn_endorsed_purchase_order,
                        self.env._("Endorsed Purchase Order"),
                    ),
                    (
                        move.l10n_tn_endorsed_purchase_order_date,
                        self.env._("Endorsed Purchase Order Date"),
                    ),
                    (
                        move.l10n_tn_endorsed_purchase_order_file,
                        self.env._("Endorsed Purchase Order File"),
                    ),
                )
                if not value
            ]
            if missing:
                move.l10n_tn_tax_exemption_missing_warning = self.env._(
                    "Tax exemption information is incomplete. Please fill in: "
                    "%(fields)s.",
                    fields=", ".join(missing),
                )

    @api.depends(
        "partner_id",
        "partner_id.commercial_partner_id",
        "invoice_date",
        "l10n_tn_is_domestic_transaction",
        "state",
        "move_type",
    )
    def _compute_l10n_tn_tax_exemption_id(self):
        for move in self:
            if not move.is_sale_document():
                move.l10n_tn_tax_exemption_id = False
                continue
            # keep the certificate used on a posted document for its audit trail
            if move.state == "posted":
                continue
            if not move.partner_id or not move._is_tax_exemption_applicable():
                move.l10n_tn_tax_exemption_id = False
                continue
            date = move.invoice_date or fields.Date.context_today(move)
            move.l10n_tn_tax_exemption_id = self.env["l10n_tn.tax_exemption"].search(
                [
                    ("partner_id", "=", move.partner_id.commercial_partner_id.id),
                    ("date_start", "<=", date),
                    ("date_end", ">=", date),
                ],
                limit=1,
            )

    @api.depends(
        "l10n_tn_tax_exemption_id.fiscal_position_id",
        "partner_id.property_account_position_id",
        "l10n_tn_is_domestic_transaction",
    )
    def _compute_fiscal_position_id(self):
        moves = self.filtered(
            lambda move: move.state != "posted" or not move.is_sale_document()
        )
        res = super(AccountMove, moves)._compute_fiscal_position_id()
        for move in moves.filtered(lambda move: move.is_sale_document()):
            exemption = move.l10n_tn_tax_exemption_id
            if (
                exemption
                and exemption.fiscal_position_id
                and move._is_tax_exemption_applicable()
            ):
                move.fiscal_position_id = exemption.fiscal_position_id
            elif move.company_id.chart_template == "tn":
                partner = move.partner_id.with_company(move.company_id)
                move.fiscal_position_id = partner.property_account_position_id
        return res

    @api.onchange("fiscal_position_id")
    def _onchange_fpos_id_show_update_fpos(self):
        res = super()._onchange_fpos_id_show_update_fpos()
        if (
            self.state == "draft"
            and self.company_id.chart_template == "tn"
            and self.is_sale_document()
            and self.invoice_line_ids
        ):
            # temporary form records must not trigger database synchronization
            lines_to_recompute = self.env["account.move.line"]
            for line in self.invoice_line_ids:
                if line.display_type in (
                    "line_section",
                    "line_subsection",
                    "line_note",
                ):
                    continue
                if not line.price_unit:
                    lines_to_recompute |= line
                    continue
                new_taxes = line._get_computed_taxes()
                if line.tax_ids.filtered("price_include") != new_taxes.filtered(
                    "price_include"
                ):
                    line.price_unit = (
                        line.product_id._get_tax_included_unit_price_from_price(
                            line.price_unit,
                            line.tax_ids,
                            fiscal_position=self.fiscal_position_id,
                            product_taxes_after_fp=new_taxes,
                        )
                    )
            lines_to_recompute._compute_price_unit()
            self.invoice_line_ids._compute_tax_ids()
            self.line_ids._compute_account_id()
            self.show_update_fpos = False
        return res

    def _is_tax_exemption_applicable(self):
        self.ensure_one()
        return self.is_sale_document() and self.l10n_tn_is_domestic_transaction

    def _post(self, soft=True):
        for move in self:
            exemption = move.l10n_tn_tax_exemption_id
            if move.state != "draft" or not move.is_sale_document() or not exemption:
                continue
            date = move.invoice_date or fields.Date.context_today(move)
            if (
                not exemption.date_start
                or not exemption.date_end
                or not exemption.date_start <= date <= exemption.date_end
            ):
                raise ValidationError(
                    self.env._(
                        "Cannot post %(invoice)s dated %(invoice_date)s: tax "
                        "exemption %(exemption)s does not cover the invoice date "
                        "(valid from %(start)s to %(end)s). Select a valid "
                        "exemption, or remove it and update taxes before posting.",
                        invoice=move.display_name,
                        invoice_date=format_date(self.env, date),
                        exemption=exemption.display_name,
                        start=(
                            format_date(self.env, exemption.date_start)
                            if exemption.date_start
                            else self.env._("Not provided")
                        ),
                        end=(
                            format_date(self.env, exemption.date_end)
                            if exemption.date_end
                            else self.env._("Not provided")
                        ),
                    )
                )
        return super()._post(soft=soft)

    @api.constrains(
        "l10n_tn_tax_exemption_id", "partner_id", "company_id", "state", "move_type"
    )
    def _check_tax_exemption_country(self):
        for move in self:
            if move.l10n_tn_tax_exemption_id and (
                not move.is_sale_document()
                or (move.state != "posted" and not move._is_tax_exemption_applicable())
            ):
                raise ValidationError(
                    self.env._(
                        "Tunisian tax exemption is only available on customer "
                        "invoices and credit notes where both the company and "
                        "the invoice partner are based in Tunisia."
                    )
                )
