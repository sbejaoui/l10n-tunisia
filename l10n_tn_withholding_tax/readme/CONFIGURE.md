This module does not create any journal or rule. You set them up in two
steps.

**Withholding tax journals**

1.  Go to *Accounting \> Configuration \> Journals*.
2.  Create (or open) a journal of type **Bank**. Use one journal per
    withholding tax rate.
3.  Open the **Advanced Settings** tab and, in the **Withholding Tax**
    section, tick **Journal includes Withholding Tax**.
4.  Set the **Rate** of the withholding tax.

The **Withholding Tax** section is only shown on journals of type
**Bank**.

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

Configure the withholding journal's manual payment method with an explicit
tax account in **Outstanding Receipts/Payments Account**:

| Withholding flow | Payment method | Tax account type | Withholding entry |
| --- | --- | --- | --- |
| Customer invoice | Inbound | Current Assets (`asset_current`) | Debit tax receivable, credit the invoice's customer account |
| Vendor bill | Outbound | Current Liabilities (`liability_current`) | Debit the invoice's supplier account, credit tax payable |

Use dedicated reconcilable tax accounts, separate from the customer/supplier
accounts and bank accounts. Configure account numbers according to the company's
chart of accounts; the module does not prescribe them. The journal's default
bank account is not the tax account: the withholding payment must use the
account configured on its payment method. Configure separate journals for
customer and supplier flows, even though the current version does not yet
enforce journal direction.

For a gross invoice of 2,000 and a withholding of 30, register a withholding
payment of 30 and a bank payment of 1,970. Reconcile both payment counterpart
lines with the invoice. The invoice total stays 2,000 and its residual becomes
zero; only the net payment affects the bank or its normal outstanding account.

Certificate confirmation changes the workflow and records the user and date.
It must not change accounts, debit/credit amounts, residuals or reconciliations,
or create another journal entry. The tax receivable/payable remains open after
confirmation; its subsequent tax settlement is a separate operation.
