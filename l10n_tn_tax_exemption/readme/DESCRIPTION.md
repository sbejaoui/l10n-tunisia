This module records Tunisian tax exemption attestations on partners. An
attestation has a number, a validity period, and a fiscal position.

When an invoice is created, the module looks for an attestation valid
for the invoice date and the customer's commercial partner. It selects
the attestation automatically and applies its fiscal position, which
maps the invoice's taxes. If the invoice date is empty, today's date is
used for the lookup.

The attestation number and validity dates are shown on the printed
invoice. The module does not create taxes or change tax rates itself;
the fiscal position's tax mappings determine the result.
