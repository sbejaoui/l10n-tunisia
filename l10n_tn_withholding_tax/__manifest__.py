# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Withholding Tax",
    "summary": "Adds Tunisian Withholding Tax handling on invoices",
    "version": "18.0.1.0.0",
    "countries": ["tn"],
    "category": "Accounting/Localizations/Account Charts",
    "author": "Sobware, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-tunisia",
    "license": "AGPL-3",
    "depends": ["l10n_account_withholding_tax", "l10n_tn"],
    "data": [
        "security/ir.model.access.csv",
        "views/journal_include_withholding.xml",
        # "views/rs_eligible_alert.xml",
        "views/withholding_rule_views.xml",
        "views/account_payment_register_views.xml",
    ],
    "installable": True,
    "application": False,
}
