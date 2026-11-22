# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Withholding Tax",
    "summary": "Adds Tunisian Withholding Tax handling on invoices",
    "version": "19.0.1.1.0",
    "countries": ["tn"],
    "category": "Accounting/Localizations/Account Charts",
    "author": "Sobware, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-tunisia",
    "license": "AGPL-3",
    "depends": ["account", "l10n_tn_account_base"],
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_tn_payment_register_withholding_line.xml",
        "views/account_journal_views.xml",
        "views/account_payment_views.xml",
        "views/l10n_tn_withholding_rule_views.xml",
        "wizard/account_payment_register_views.xml",
        "report/report_invoice.xml",
    ],
    "installable": True,
    "application": False,
}
