The Tunisian chart template creates the bank-type journal TRT and its inbound
Traite payment method. The method uses the chart's bills-receivable account
(reference l10n_tn_413). The technical journal is hidden from the bank dashboard.

For an existing Tunisian company, open the company's Traites tunisiennes page
and use Ajouter le journal Traites depuis le plan comptable. This adds missing
bill records only. It does not reload accounts or overwrite an existing
journal's customized name.

Validate the accounts with the company's accountant. The bills account must
be receivable, reconcilable, different from the customer account and different
from the journal's default bank account. Actual bank/cash receipts use the
method's configured outstanding account when present. Otherwise, Odoo resolves
its default receipts account, falling back to the company's transfer account.
An accounting entry is required to settle the bill, and the resolved collection
account must differ from the bill counterpart account. A cash method can use
the cash account directly.

Set a follow-up manager, reminder lead time and escalation delay on the company.
Daily activities stay internal: no automatic email or reminder is sent to the
debtor.
