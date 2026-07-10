This module adds Tunisian stamp tax (*droit de timbre*) handling on invoices.

It does **not** ship any tax of its own. Instead, it adds an **Is Stamp Tax**
flag on taxes: you tick it on the fixed-amount tax you use as the stamp tax,
and the module takes care of the rest.

When a customer or vendor invoice is posted for a Tunisian company and a
Tunisian partner, a stamp tax line is automatically appended if one is not
already present. The line carries the flagged stamp tax, so the amount is
reflected in the invoice totals and the tax report like any other tax.

The correct sale or purchase stamp tax is selected automatically based on the
document type and the company.

On the printed invoice (PDF), the stamp tax line is hidden from the invoice
line table, so it does not appear as a product line; the amount still shows in
the tax summary.
