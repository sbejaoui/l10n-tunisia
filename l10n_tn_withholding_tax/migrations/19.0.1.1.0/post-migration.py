# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    payments = env["account.payment"].search(
        [("journal_id.is_withholding_tax_journal", "=", True)]
    )
    payments._compute_state()
    payments._compute_reconciliation_status()
    invoices = (
        payments.invoice_ids
        | payments.reconciled_invoice_ids
        | payments.reconciled_bill_ids
    )
    invoices._compute_payment_state()
