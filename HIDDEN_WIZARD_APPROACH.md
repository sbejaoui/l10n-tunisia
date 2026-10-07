# Multiple-bill withholding payments: hidden wizard approach

## The problem

With one bill, the withholding payment wizard correctly calculates a partial payment for
that bill. With several bills selected, a grouped payment contains one combined
withholding amount. Odoo then has no per-bill withholding amount to reconcile, so the
payment can be consumed by the first bill.

The goal is to create one withholding payment per bill, with each payment reconciled
only with its own bill.

## Why `_create_payments` is overridden

`_create_payments` is the method that actually creates the payment records after the
user presses **Create Payment**. It is a good place to customize the workflow because
the wizard is ready to create payments, but no payment has been created yet.

The approach is:

1. Detect a withholding-tax payment for multiple bills.
2. Create a temporary payment wizard for each bill in Python.
3. Give the temporary wizard the same journal, payment date, and payment method selected
   in the main wizard.
4. Calculate the withholding amount for that one bill.
5. Let Odoo create and reconcile that one payment normally.

The temporary wizards are never opened in the user interface.

## Code walkthrough

```python
def _create_payments(self):
    self.ensure_one()
```

This overrides Odoo's payment-creation method. `ensure_one()` checks that the method is
working with one main wizard record, which is the normal case when a user opens the
payment wizard.

```python
    if not (
        self.journal_id.is_withholding_tax_journal
        and self.has_multiple_bills
    ):
        return super()._create_payments()
```

This protects normal Odoo behavior. If the selected journal is not a withholding
journal, or the wizard has only one bill, the code calls Odoo's original method through
`super()`.

```python
    payments = self.env["account.payment"]
```

This creates an empty Odoo recordset. It will collect the payments created for each
bill.

```python
    for bill in self.line_ids.move_id:
```

`line_ids` contains the payable or receivable lines selected in the payment wizard. Each
line belongs to an accounting move, which is available through `move_id`. The loop
therefore handles every selected bill one at a time.

```python
        payment_wizard = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=[bill.id],
        ).create({})
```

This creates a new payment wizard directly in Python. The context tells Odoo that the
wizard is being opened for the current `bill` only:

- `active_model="account.move"` says that the active record is a bill.
- `active_ids=[bill.id]` provides that single bill's ID.

Because it is created with `.create({})`, no wizard form appears in the user interface.
Odoo uses the context to initialize its `line_ids` with that bill's payable or
receivable line.

```python
        payment_wizard.journal_id = self.journal_id
        payment_wizard.payment_date = self.payment_date
        payment_wizard.payment_method_line_id = self.payment_method_line_id
```

These assignments copy the user's choices from the main wizard to the temporary wizard:
the same withholding journal, payment date, and payment method.

```python
        payment_wizard._calculate_withholding_amount()
```

This calls the module's existing withholding calculation. Since the temporary wizard
contains only one bill, it calculates that bill's withholding amount rather than a total
across all selected bills.

For example:

```text
Bill A: 1,000 x 1% = 10
Bill B: 2,000 x 1% = 20
```

```python
        payments |= payment_wizard._create_payments()
```

The temporary wizard creates and reconciles its payment through the normal Odoo process.
`|=` adds the returned payment record to the `payments` recordset.

The temporary wizard has only one bill, so `has_multiple_bills` is false for it. Its
call to `_create_payments()` therefore reaches `super()` and uses Odoo's original
implementation. This prevents the code from creating another set of temporary wizards.

```python
    return payments
```

After every bill is handled, all created payments are returned to the main wizard. Odoo
can then show the list of created payments.

## Why automatic Group Payments was removed

The code previously set:

```python
self.group_payment = True
```

when a withholding journal was chosen for several bills. It was removed because this
hidden-wizard approach does not need one grouped payment. Its goal is the opposite: one
partial withholding payment per bill.

Leaving the checkbox automatically ticked would be misleading: the screen would say
**Group Payments**, while the custom code deliberately creates separate payments in the
background.

## What the Group Payments checkbox normally does

In standard Odoo, **Group Payments** changes how several bills are paid:

- Enabled: Odoo tries to create one combined payment for compatible bills, usually bills
  for the same partner with compatible payment details.
- Disabled: Odoo creates separate payments, normally one payment per bill.

It is useful for an ordinary bank payment where a supplier is paid one total amount
covering several invoices. It is not suitable for this withholding case: the combined
payment is a partial amount and Odoo does not know how much of it belongs to each bill.

## Short explanation

> I intercept payment creation only for multiple withholding-tax bills. I create a
> temporary payment wizard for each bill, copy the selected payment settings, calculate
> that bill's withholding amount, and let Odoo create and reconcile its payment
> normally. This produces one partial payment per bill instead of one combined amount
> consumed by the first bill.

## Testing note

This is a proof-of-concept implementation. Test it with two eligible, posted, unpaid
bills first. Further testing should cover different vendors, currencies, partial
payments, and bills with different withholding rules.
