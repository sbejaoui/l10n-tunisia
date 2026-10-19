This module records Tunisian tax exemption attestations on partners. An
attestation has a number, a validity period, and a fiscal position.

When an invoice is created, the module looks for an attestation valid
for the invoice date and the customer's commercial partner. It selects
the attestation automatically and applies its fiscal position, which
maps the invoice's taxes. If the invoice date is empty, today's date is
used for the lookup.

The module creates a 0% sales tax named **Tax exonerated**. The fiscal
position's tax mappings determine whether it is applied to invoice lines.

When an attestation is selected, its number and start date are shown on
the printed invoice, along with the Bon de Commande Visé number and date.
