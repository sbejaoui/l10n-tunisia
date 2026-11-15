# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Stamp Tax",
    "summary": "Configures chart stamp taxes and handles them on Tunisian invoices",
    "version": "19.0.1.0.0",
    "countries": ["tn"],
    "category": "Accounting/Localizations/Account Charts",
    "author": "Sobware, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-tunisia",
    "license": "AGPL-3",
    "depends": ["account", "l10n_tn_account_base"],
    "post_init_hook": "post_init_hook",
    "data": [
        "views/is_stamp_tax.xml",
        "report/report_invoice_document_stamp_tax.xml",
    ],
    "installable": True,
    "application": False,
}
