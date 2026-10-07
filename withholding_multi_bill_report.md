# Debugging report: paying several bills with a withholding journal pays the full bills

|                  |                            |
| ---------------- | -------------------------- |
| **Module**       | `l10n_tn_withholding_tax`  |
| **Prepared by**  | Rami                       |
| **Date**         | 16 September 2026          |
| **Odoo version** | 18.0                       |
| **Branch**       | `withholding-tax`          |
| **Status**       | Cause found, not fixed yet |

## Summary

When I select several bills and pay them with a withholding tax journal, the wizard
shows the correct withholding amount. But when I click the button, Odoo creates one
payment per bill for the **full** amount due.

The cause is in Odoo's payment wizard. When more than one bill is selected and _Group
Payments_ is not ticked, Odoo does not use the Amount field at all. It builds each
payment from the amount still due on the bill. Our module only changes the Amount field,
so our withholding amount is ignored.

## Steps to reproduce

1. Create and post two vendor bills for the same vendor, using a product that has a
   withholding rule.
2. In the bills list, select both bills and click **Pay**.
3. The wizard shows the withholding alert with the correct amount.
4. Choose the withholding tax journal. The Amount changes to the withholding amount.
5. Leave _Group Payments_ unticked and click **Create Payments**.

**Expected:** payments for the withholding amount only.

**What happened:** two payments, each for the full bill amount. Both bills end up fully
paid.

## What I found in the code

All Odoo files below are in `addons/account/wizard/` unless another path is given.

### 1. The line that decides how payments are built

I looked for the method that runs when clicking Create Payments. It is
`_create_payments()` in `account_payment_register.py` (line 1208). Near the top, one
line decides which way the payments will be built:

`account_payment_register.py`, line 1225:

```python
edit_mode = self.can_edit_wizard and (len(first_batch_result['lines']) == 1 or self.group_payment)
```

I didn't know what `edit_mode` meant, so I checked each part:

- `can_edit_wizard` is True when all selected bills fit in one "batch": same vendor,
  same account, same currency and same bank account. It is set in
  `_compute_from_lines()`, lines 434–438.
- `len(first_batch_result['lines']) == 1` is True only when a single bill is selected.
- `group_payment` is the _Group Payments_ checkbox. By default it is only ticked when
  there is one bill:

`account_payment_register.py`, lines 479–484:

```python
def _compute_group_payment(self):
    for wizard in self:
        if wizard.can_edit_wizard:
            wizard.group_payment = len(wizard.batches[0]['lines'].move_id) == 1  # False with 2 bills
        else:
            wizard.group_payment = False
```

### 2. The values in my test

| Value                  | In my test  | Why                                                           |
| ---------------------- | ----------- | ------------------------------------------------------------- |
| `can_edit_wizard`      | `True`      | Both bills are from the same vendor, so they are in one batch |
| Number of lines `== 1` | `False`     | Two bills are selected                                        |
| `group_payment`        | `False`     | More than one bill, and I didn't tick it                      |
| **`edit_mode`**        | **`False`** | `True and (False or False)`                                   |

### 3. The two ways Odoo builds a payment

After that line, `_create_payments()` goes one of two ways:

`account_payment_register.py`, lines 1228–1264 (shortened):

```python
if edit_mode:
    payment_vals = self._create_payment_vals_from_wizard(first_batch_result)
    ...
else:
    if not self.group_payment:
        # Don't group payments: Create one batch per move.
        ...
    for batch_result in batches:
        to_process.append({
            'create_vals': self._create_payment_vals_from_batch(batch_result),
```

**When `edit_mode` is True**, the payment amount is taken from the Amount field in the
wizard:

`account_payment_register.py`, lines 982–985:

```python
def _create_payment_vals_from_wizard(self, batch_result):
    payment_vals = {
        'date': self.payment_date,
        'amount': self.amount,  # <-- uses the Amount field
```

**When `edit_mode` is False** (my case), Odoo first splits the selection into one batch
per bill, then builds each payment with a different method:

`account_payment_register.py`, lines 1043–1058 (shortened):

```python
def _create_payment_vals_from_batch(self, batch_result):
    batch_values = self._get_wizard_values_from_batch(batch_result)
    ...
    payment_vals = {
        'date': self.payment_date,
        'amount': batch_values['source_amount_currency'],  # <-- does NOT use the Amount field
```

I followed `source_amount_currency` into `_get_wizard_values_from_batch()`. It is
calculated from what is still due on the bill:

`account_payment_register.py`, line 297:

```python
source_amount = abs(sum(lines.mapped('amount_residual')))
```

So in this path, `self.amount` is never read. Each payment gets the full amount still
due on its bill, which is exactly what I saw.

## Why the wizard still showed the right amount

This confused me at first, because the numbers on screen were correct. There are two
reasons:

- The blue alert comes from `_compute_withholding_tax_alert()` in our module. It only
  displays text and is not used when the payments are created.
- The Amount is changed by our onchange, which sets `self.amount`:

[`l10n_tn_withholding_tax/models/account_payment_register.py`](l10n_tn_withholding_tax/models/account_payment_register.py#L13-L18),
lines 13–18:

```python
@api.onchange("journal_id")
def _calculate_withholding_amount(self):
    if self.journal_id.is_withholding_tax_journal:
        total_amount = sum(move.amount_total for move in self.line_ids.move_id)
        withholding_amount = total_amount * self.journal_id.withholding_tax_rate
        self.amount = withholding_amount
```

In Odoo's view, the Amount field is read-only in this situation (`can_group_payments` is
True and `group_payment` is False):

`account_payment_register_views.xml`, lines 109–111:

```xml
<field
  name="amount"
  force_save="1"
  readonly="not can_edit_wizard or can_group_payments and not group_payment"
/>
```

The user can't edit a read-only field, but an onchange can still change the value that
is displayed. So the right number shows up on screen, but Odoo doesn't use it when it
creates the payments.

> A hint I missed: the button said **Create Payments** (plural). The view shows that
> label when Odoo is going to create more than one payment
> (`account_payment_register_views.xml`, line 134).

## Test to confirm

I repeated the same steps, but this time I ticked _Group Payments_. Now `group_payment`
is True, so `edit_mode` is True and Odoo uses `_create_payment_vals_from_wizard()`.

**Result:** one payment was created for the withholding amount of both bills together.
This confirms that the Amount field is only used in edit mode.

## Side effect of the grouped payment

With the grouped payment, the withholding amount was taken off only **one** of the two
bills. The other bill stayed as it was. I checked why in `_reconcile_payments()`
(`account_payment_register.py`, lines 1176–1206):

- Odoo reconciles the payment with both bills at the same time (line 1205).
  Reconciliation sorts the lines by due date
  (`addons/account/models/account_move_line.py`, lines 2427–2429), so the oldest bill
  uses up the whole payment.
- After that, line 1206 links the payment to both bills:

  ```python
  lines.move_id.matched_payment_ids += payment
  ```

  Our `is_rs_paid` and `is_withholding_tax_rule_applied()` read `matched_payment_ids`,
  so I expect both bills to show "RS already paid", even the one that wasn't reduced.
  _(I haven't tested this part yet.)_

## Conclusion

This is not a bug in Odoo. The wizard only uses the Amount field when it is in edit
mode, which means one bill is selected or _Group Payments_ is ticked. Our module sets
the withholding amount by changing the Amount field, so it only works in edit mode. With
several bills and _Group Payments_ unticked, Odoo calculates each payment from the
amount due on the bill, and our amount is lost.

## Questions and next steps

- Ask the accounting side: should the withholding tax be **one payment per bill**, or
  can one payment cover several bills?
- If it should be one payment per bill: the amount for each bill is decided in
  `_create_payment_vals_from_batch()`, so that looks like the place to change it.
- Decide what should happen when one of the selected bills is below the rule's
  threshold.
- Something else I noticed: `_get_withholding_amount()` in
  [`withholding_rule.py`](l10n_tn_withholding_tax/models/withholding_rule.py#L44-L47)
  adds up all selected bills. With a 1,000 threshold, if bill A is 1,500 and bill B is
  500, the withholding is calculated on 2,000, even though bill B is below the
  threshold.
