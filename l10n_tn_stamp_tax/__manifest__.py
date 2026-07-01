{
    "name": "Stamp Tax",
    "summary": "Adds Tunisian stamp tax handling on invoices",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "author": "Rami Brick",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "data/account_tax.xml",
        "data/tva.xml",
        "data/fodec.xml",
        "report/report_invoice_document_stamp_tax.xml",
    ],
    "installable": True,
    "application": False,
}
