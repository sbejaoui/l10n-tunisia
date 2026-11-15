# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    l10n_tn_bon_de_commande_vise = fields.Char(string="Bon de Commande Visé")
    l10n_tn_bon_de_commande_vise_date = fields.Date(string="Bon de Commande Visé Date")
    l10n_tn_bon_de_commande_vise_file = fields.Binary(
        string="Bon de Commande Visé File",
        attachment=True,
        copy=False,
    )
    l10n_tn_bon_de_commande_vise_filename = fields.Char(copy=False)

    @api.depends(
        "partner_id.commercial_partner_id",
        "invoice_date",
        "l10n_tn_is_domestic_transaction",
        "state",
    )
    def _compute_l10n_tn_tax_exemption_id(self):
        for move in self:
            # keep the certificate used on a posted document for its audit trail
            if move.state == "posted":
                continue
            if not move._is_tax_exemption_applicable():
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

    @api.depends("l10n_tn_tax_exemption_id", "l10n_tn_is_domestic_transaction")
    def _compute_fiscal_position_id(self):
        drafts = self.filtered(lambda move: move.state != "posted")
        res = super(AccountMove, drafts)._compute_fiscal_position_id()
        for move in drafts:
            exemption = move.l10n_tn_tax_exemption_id
            if exemption and move._is_tax_exemption_applicable():
                move.fiscal_position_id = exemption.fiscal_position_id
        return res

    def _is_tax_exemption_applicable(self):
        self.ensure_one()
        return self.l10n_tn_is_domestic_transaction

    @api.constrains("l10n_tn_tax_exemption_id", "partner_id", "company_id", "state")
    def _check_tax_exemption_country(self):
        for move in self:
            if (
                move.l10n_tn_tax_exemption_id
                and not move._is_tax_exemption_applicable()
            ):
                raise ValidationError(
                    self.env._(
                        "Tunisian tax exemption requires both the company and "
                        "the invoice partner to be based in Tunisia."
                    )
                )
