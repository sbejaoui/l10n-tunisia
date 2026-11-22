This module does not create any journal or rule. You set them up in two
steps.

**Withholding tax journals**

1.  Go to *Accounting \> Configuration \> Journals*.
2.  Create (or open) a journal of type **Bank** for the withholding rate.
    The same journal may serve customer and supplier withholding.
3.  Tick **Withholding tax journal**, next to the journal type.
4.  In **Withholding Tax**, enter the rate as a percentage, for example
    `1.5` for 1.5%.
5.  Configure fiscal accounts on the payment methods in Odoo's standard
    **Incoming Payments** and **Outgoing Payments** tabs. Incoming payments
    use the customer withholding account; outgoing payments use the supplier
    withholding account. There is no additional account field on the journal.

Separate journals for customer and supplier withholding are optional. Use the
rule's **Document Type** to restrict a rule to customer invoices or vendor bills.

**Withholding rules**

1.  Go to *Accounting \> Configuration \> Withholding Rules*.
2.  Create a rule and fill in:
    - **Article**: the products the rule applies to. Leave empty to apply
      the rule to any invoice meeting the minimum amount.
    - **Description**: a short explanation of the rule.
    - **Document Type**: **Customer Invoice** (`out_invoice`) or **Vendor Bill**
      (`in_invoice`). Leave empty to apply to both. The same journal may
      be used by rules for either document type.
    - **Amount**: the minimum bill total (taxes included) from which the
      withholding applies. The threshold is inclusive. Use 0 for no minimum.
      This amount cannot be negative.
    - **Withholding Tax Journal**: the journal holding the rate to
      apply. Only journals with **Journal includes Withholding Tax**
      ticked can be selected.

Product rules are filtered by company, document type and
minimum amount before selecting the highest applicable threshold (then the
lowest rule ID in case of a tie). Rules without products follow the same
compatibility checks. Alerts, available journals and invoice allocation
proposals use this selection.

**Accounting reference**

Use Odoo's standard outstanding receipt/payment account on each payment method.
A shared journal can use different accounts for incoming and outgoing payments:

| Withholding flow | Payment method | Example tax account | Withholding entry |
| --- | --- | --- | --- |
| Customer invoice | Inbound | 434100, withholding suffered | Debit tax receivable, credit the invoice's customer account |
| Vendor bill | Outbound | 432000, withholding owed to the State | Debit the invoice's supplier account, credit tax payable |

Use dedicated tax accounts, separate from the customer/supplier accounts and
bank accounts. Configure account numbers according to the company's chart of
accounts; these examples are not enforced. Odoo's Tunisian chart supplies both
432 and 4341 as Current Liabilities (`liability_current`), without reconciliation
enabled. The module accepts Current Assets (`asset_current`) and Current
Liabilities for either flow, without requiring reconciliation on the fiscal
account. The payment direction determines the debit/credit entry. Invoice
counterpart lines are still reconciled on their customer/supplier account.
Account types still affect financial report classification; accepting an
account does not verify or correct its presentation in those reports.

The journal's default bank account is not the tax account: withholding must use
its selected payment method's fiscal account, for the actual payment direction.

A withholding journal must have type **Bank** and a valid rate. A configured
payment method account must be active, available to the journal's company and
of type Current Assets or Current Liabilities. It must differ from the journal's default bank account and the company's transfer
account. A forced account currency must also match the payment currency.

The rate is stored as a fraction: `0 < rate <= 1`, where `0.015` means 1.5%
and `1` means 100%. The journal form displays and accepts percentages.

You may save a journal while its payment method account is still empty, to
finish configuration afterward. Creating or posting a withholding payment
requires an explicit fiscal account on the selected method. Direct ORM calls
and forced journal entry generation follow the same rule; the payment's actual
account and generated entry must match that configured account. Withholding
payments cannot fall back to a normal outstanding or transfer account. Regular
bank/cash payments keep Odoo's standard behavior.

Configuration remains editable as long as it is valid. The module does not
freeze the journal or its accounts after a payment has been posted. Changing
the rate or payment method account affects future payments without rewriting
existing journal entries. Changing a journal's withholding flag also
changes the withholding classification of payments linked to that journal.

For a gross invoice of 2,000 and a withholding of 30, register a withholding
payment of 30 and a bank payment of 1,970. Reconcile both payment counterpart
lines with the invoice. The invoice total stays 2,000 and its residual becomes
zero; only the net payment affects the bank or its normal outstanding account.

Certificate confirmation changes the workflow and records the user and date.
It must not change accounts, debit/credit amounts, residuals or reconciliations,
or create another journal entry. The tax receivable/payable balance remains
after confirmation; its subsequent tax settlement is a separate operation.
On a non-reconcilable fiscal account, follow this balance in the general ledger,
rather than using the line's residual amount.

Use the payment's reset, cancel or reject actions to clear certificate
confirmation and its audit fields. Direct ORM state changes that leave
confirmation on a draft, canceled or rejected withholding payment are refused.

New withholding payments are supported only for customer receipts and supplier
payments. Customer refunds and supplier reimbursements use regular bank/cash
payments, without new withholding. This also applies to direct ORM creation or
updates, including a refund document linked to an otherwise normal payment.
Reversing or settling the tax balance of an earlier withholding is a separate
operation, outside this workflow.

The certificate confirmation action is available to accounting users with write
access to the payment and a posted journal entry. It records the current user
and server date, and checks every payment in a batch before updating any
certificate. Direct ORM updates are allowed under standard access rights when
the certificate, date and user are consistent and the withholding payment has
a posted journal entry. Clear all three fields together when resetting through
the ORM; the standard reset, cancel and reject actions do this automatically.

A withholding payment stays **In Process** until its certificate is confirmed
and its journal entry is posted. If the entry is reset directly to draft, the
payment returns to **In Process** and is no longer matched; the certificate
metadata remains recorded. Posting that entry again restores **Paid** when the
certificate is still confirmed. Resetting the payment itself, canceling it or
rejecting it clears the confirmation and preserves the selected lifecycle state.
Regular payments retain Odoo's standard state computation.

Invoice withholding status and duplicate-rule checks follow the current
reconciliations on the customer/supplier journal items. A historical payment
association alone does not count. Unreconciling a withholding makes its rule
available again for the remaining balance. Reassigning the payment to another
invoice transfers certificate tracking to that invoice. A fully settled invoice
stays **In Payment** while any currently reconciled withholding is awaiting its
certificate; confirming one withholding does not confirm the others. The same
withholding payment may be partially reconciled to several invoices.
