Once the attestation and its fiscal position are configured (see
*Configuration*), the attestation is selected automatically:

Exemption applies only to customer invoices and customer credit notes when
both the company and partner have Tunisia as their country. Vendor documents,
receipts, journal entries, and documents with a missing country are ineligible.
Exemption fields are hidden for other transactions, and manually assigning a
certificate to an ineligible document is rejected.

1.  Create a customer invoice or credit note and set an **Invoice Date**
    within the attestation's validity period.
2.  On the **Other Info** tab, check that **Tax Exemption** shows the
    attestation and **Fiscal Position** shows its fiscal position. Enter
    the **Endorsed Purchase Order** number and date, and attach its file if
    available.
3.  Add the invoice lines and check their taxes. For sales taxes mapped to
    **Tax Exemption**, the lines should show that 0% tax. On draft Tunisian
    invoices, changing the fiscal position in the form automatically updates
    existing line taxes and accounts. Check the taxes again before posting.
4.  Preview or print the invoice to see the attestation number and issue
    date, along with the Endorsed Purchase Order number and date.

The lookup uses the commercial partner, so an invoice addressed to a
child contact can use an attestation configured on its parent company.
If no attestation matches, the **Tax Exemption** field stays empty.
For Tunisian companies, the invoice uses the partner's configured fiscal
position in that case, or clears it if the partner has none. Changing the
partner or invoice date recalculates the attestation and fiscal position.
Check the fiscal position and invoice-line taxes before posting.

Changing countries re-evaluates exemption on draft documents. Certificates and
fiscal positions already recorded on posted documents are preserved.

When an exemption is selected on a draft customer invoice or credit note, an
information banner previews the legal message printed on the report. A separate
warning lists missing details: attestation number or issue date, fiscal position,
and Endorsed Purchase Order number, date, or attachment. These alerts are hidden
outside draft state; the legal message remains on the printed report.
