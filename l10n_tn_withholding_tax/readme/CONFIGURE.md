This module does not create any journal or rule. You set them up in two
steps.

**Withholding tax journals**

1.  Go to *Accounting \> Configuration \> Journals*.
2.  Create (or open) a journal of type **Bank**. Use one journal per
    withholding tax rate and direction.
3.  Tick **Withholding tax journal**, next to the journal type.
    This displays the **Withholding Tax** tab.
4.  Open that tab and choose the **Withholding flow**:
    **Customer withholding (received)** or **Supplier withholding (deducted)**.
5.  Enter the **Withholding rate** as a percentage, for example `1.5` for 1.5%.
6.  Select the **Tax receivable account** for customer withholding or the
    **Tax payable account** for supplier withholding. The account selector
    proposes active Current Assets or Current Liabilities accounts for the
    journal's company. Reconciliation on the fiscal account is optional.
    If you create an account from the selector, its type and company are
    prefilled.

The checkbox is shown only on journals of type **Bank**. The dedicated tab
appears first when withholding is enabled. The account is configured directly
on the journal; editing a payment-method table is not required. The standard
bank settings are hidden for withholding journals. Fiscal accounts are visible
to accounting administrators even when the full accounting interface is not
enabled.

The account field updates the default manual payment method for the selected
direction. If that method is missing, a message directs you to the standard
payment tab to add it, then return to select the account.

**Withholding rules**

1.  Go to *Accounting \> Configuration \> Withholding Rules*.
2.  Create a rule and fill in:
    - **Article**: the products the rule applies to. Leave empty to apply
      the rule to any invoice meeting the minimum amount.
    - **Description**: a short explanation of the rule.
    - **Document Type**: **Customer Invoice** (`out_invoice`) or **Vendor Bill**
      (`in_invoice`). Leave empty to apply the rule to both.
    - **Amount**: the minimum bill total (taxes included) from which the
      withholding applies. The threshold is inclusive. Use 0 for no minimum.
      This amount cannot be negative.
    - **Withholding Tax Journal**: the journal holding the rate to
      apply. Only journals with **Journal includes Withholding Tax**
      ticked can be selected.

**Accounting reference**

Select the tax account directly in **Withholding Tax > Accounting**. This
field edits Odoo's standard outstanding payment/receipt account on the manual
method, with no separate stored account setting:

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
account. The journal's direction determines the debit/credit entry. Invoice
counterpart lines are still reconciled on their customer/supplier account.
Account types still affect financial report classification; accepting an
account does not verify or correct its presentation in those reports.

The journal's default bank account is not the tax account: the withholding
payment must use the
account configured on its payment method. Configure separate journals for
customer and supplier flows. Journal direction is mandatory; filtering rules
and validating payment compatibility with that direction are subsequent
roadmap steps.

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
existing journal entries. Use a separate journal when changing the nature or
direction of a withholding flow. Changing a journal's withholding flag also
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
