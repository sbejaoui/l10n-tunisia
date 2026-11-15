# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    # preserve historical paid payments without inventing confirmation audit data
    cr.execute("""
        ALTER TABLE account_payment
        ADD COLUMN IF NOT EXISTS withholding_reception_confirmed boolean
    """)
    cr.execute("""
        UPDATE account_payment payment
           SET withholding_reception_confirmed = TRUE
          FROM account_journal journal
         WHERE payment.journal_id = journal.id
           AND journal.is_withholding_tax_journal
           AND payment.state = 'paid'
    """)
