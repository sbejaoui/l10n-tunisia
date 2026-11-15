Sales orders normally copy their fiscal position to the invoice. This module
recomputes it for sales invoices and credit notes linked to sales order lines
in companies using the Tunisian chart of accounts.

The invoice uses the exemption attestation valid for its partner and invoice
date. If the date is empty, the tax exemption module uses today's date. When
the fiscal position changes, Odoo updates the invoice's taxes and accounts.
The sales order keeps its original fiscal position and taxes.

This module installs automatically when **Sales** and **Tax Exemption for
Tunisia** are installed.
