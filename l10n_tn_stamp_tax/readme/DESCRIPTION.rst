This module adds Tunisian stamp tax (*droit de timbre*) handling on invoices.

When a customer or vendor invoice is posted, a fixed stamp tax line is
automatically appended to the invoice if one is not already present. The
stamp tax is implemented as a standard fixed-amount ``account.tax``, so it
is reflected in the invoice totals and the tax report like any other tax.

The module also ships the common Tunisian taxes used alongside the stamp
tax:

* **Stamp Tax** (*droit de timbre*) — a fixed amount per invoice, for both
  sales and purchases.
* **TVA** — the standard 19% Tunisian VAT, for sales and purchases.
* **FODEC** — the 1% *Fonds de Développement de la Compétitivité*, applied
  on the base amount before VAT, for sales and purchases.

On the printed invoice (PDF), the stamp tax is shown in the tax summary but
hidden from the invoice line table, so it does not appear as a product line.
