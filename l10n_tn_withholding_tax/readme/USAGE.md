Once the journals and rules are configured (see *Configuration*), withholding
tax is handled from the payment wizard.

Withholding applies only when both the invoice company and invoice partner have
Tunisia as their country. A missing country makes the document ineligible.
Withholding journals and alerts are not offered for ineligible documents.
Direct payment creation and confirmation enforce the same country restriction.

## One receipt for several invoices

Select several invoices for the same customer and click **Pay**. Enable
**Withholding Tax Applicable**, then choose **Keep Unpaid** or **Register
Withholding Payment**.

The checkbox is shown only when several invoices are selected and at least one
has an applicable withholding rule. It is hidden when none of the selected
invoices meets the Tunisia country restriction or matches a withholding rule.

The allocation table shows each invoice's remaining balance, applicable
withholding journals, calculated withholding amount, and cash allocation.
Different invoices can use different journals or several journals. Edit the
selected journals and cash allocations as needed; withholding amounts are
calculated from each journal's rate and the invoice's original total, rounded
per journal in the invoice currency.

Changing the bank/cash amount fills each invoice's balance after withholding in
allocation order before moving to the next invoice. Once the cash is exhausted,
later invoices receive no cash allocation. Each invoice's withholding stays
reserved. Editing cash allocations directly updates the bank/cash total while
preserving the manual distribution. An amount above the total net balance keeps
the existing allocations and displays a warning; it cannot consume withholding.

Exactly one bank/cash payment is created for the amount received. Its
reconciliation follows the cash allocation of each invoice:

- **Keep Unpaid** leaves the withholding amount outstanding on each invoice.
  No withholding payment is created.
- **Register Withholding Payment** additionally creates one pending withholding
  payment per invoice/journal. Certificate confirmation remains a separate step.

A warning shows differences from the suggested net total. Partial payments are
allowed when the edited cash allocations add up to the bank/cash amount.
Confirmation is blocked for incompatible journals, stale balances, negative or
excess allocations, or cash totals that do not match the payment. Differences
are never written off automatically.

Allocation mode supports posted customer invoices or vendor bills in the company
currency, for one partner, company and receivable/payable account. Credit notes
and foreign currencies use the standard payment flow. Existing withholding
payments are excluded from the suggested withholding journals to avoid duplicates.

## Individual withholding payments

1.  Open a posted vendor bill that meets a withholding rule's conditions,
    and click **Pay**.
2.  At the top of the wizard, a message lists the applicable withholding
    taxes, with the journal and the amount to withhold for each one.
3.  In **Journal**, select the withholding tax journal. The **Amount** is
    filled in automatically with the withholding amount.
4.  Click **Create Payment**.
5.  Pay the rest of the bill as usual with your bank journal.

A rule applies when the bill total is equal to or higher than the rule's
**Amount** and, if products are selected, the bill contains one of them.
Rules without products also apply to invoice lines without a product.
Amount-only and matching product rules can both apply. Withholding tax journals
that do not match an applicable rule are not offered in the **Journal**
field.

Once the withholding tax has been paid, its journal is no longer offered
for that bill and the rule no longer appears in the wizard.

## Invoice report with payments

When printing an invoice with payments, withholding payments appear first,
labelled with their journal name (for example **RS 1.5%**), with the reconciled
amount in the invoice currency. Other payments keep their usual labels, dates
and relative order. The invoice balance
and accounting entries are unchanged.

## Certificate confirmation

Withholding payments remain **In Process** until the certificate is confirmed.
The invoice or bill balance is reduced immediately, but a fully settled invoice
or bill remains **In Payment** while its withholding certificate is pending.

- Open **Customers > Incoming Withholding Payments** to track received
  withholding. Open a payment and click **Validate Reception** after receiving
  its certificate.
- Open **Vendors > Outgoing Withholding Payments** to track issued withholding.
  Open a payment and click **Confirm Certificate Delivery** after delivering
  its certificate.

Both menus offer kanban and list views, with filters by state, partner, journal,
date and company. Confirmation records the accounting user and date, marks the
payment **Paid**, and updates the invoice or bill when all payments are matched.
Confirmation does not create another journal entry. Resetting, canceling or
rejecting a payment clears its confirmation. Pending withholding payments still
prevent duplicate registration; canceled payments no longer block the rule.

On upgrade, existing **Paid** withholding payments are treated as confirmed.
Their confirmation user and date stay empty because no historical certificate
confirmation was recorded.
