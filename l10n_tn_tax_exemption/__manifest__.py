# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Tax Exemption for Tunisia",
    "summary": "Adds Tunisian Tax Exemption handling on invoices",
    "version": "19.0.1.0.1",
    "countries": ["tn"],
    "category": "Accounting/Localizations/Account Charts",
    "author": "Sobware, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-tunisia",
    "license": "AGPL-3",
    "depends": ["account", "l10n_tn_account_base"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "views/account_move.xml",
        "report/report_invoice.xml",
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}
