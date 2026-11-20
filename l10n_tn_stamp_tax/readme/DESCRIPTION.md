This module adds Tunisian stamp tax (*droit de timbre*) handling on
invoices.

The module automatically configures the existing sales and purchase stamp
taxes from the Tunisian chart of accounts using the **Is Stamp Tax** flag.
No duplicate taxes are created and no manual setup is required for a new chart.

When a customer or vendor invoice is posted for a Tunisian company and a
Tunisian partner, a stamp tax line is automatically appended if one is
not already present. The line carries the flagged stamp tax, so the
amount is reflected in the invoice totals and the tax report like any
other tax.

The correct sale or purchase stamp tax is selected automatically based
on the document type and the company.

On the printed invoice (PDF), the stamp tax line is hidden from the
invoice line table, so it does not appear as a product line; the amount
still shows in the tax summary.

Invoices outside this domestic scope can be posted without configured stamp
taxes. Domestic Tunisian invoices still require the appropriate stamp tax.
