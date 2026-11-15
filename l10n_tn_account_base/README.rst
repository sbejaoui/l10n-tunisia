Tunisian Accounting Base
=======================

Shared eligibility checks for Tunisian accounting addons.

A transaction is domestic when both the document's company and invoice partner
have Tunisia as their country. Missing countries are treated as ineligible.
The active company in the user's session does not affect this check.

The account.move method ``_l10n_tn_is_domestic_transaction`` provides the common
check. The computed field ``l10n_tn_is_domestic_transaction`` exposes it to views.
Stamp Tax, Tax Exemption and Withholding Tax retain their own applicability
rules and use this shared check.

This addon does not change existing posted accounting entries.
