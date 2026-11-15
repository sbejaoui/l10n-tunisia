Once the attestation and its fiscal position are configured (see
*Configuration*), the attestation is selected automatically:

Exemption applies only when both the invoice company and invoice partner have
Tunisia as their country. A missing country makes the document ineligible.
Exemption fields are hidden for other transactions, and manually assigning a
certificate to an ineligible document is rejected.

1.  Create a customer invoice for the partner and set an **Invoice Date**
    within the attestation's validity period.
2.  On the **Other Info** tab, check that **Tax Exemption** shows the
    attestation and **Fiscal Position** shows its fiscal position. Enter
    the **Bon de Commande Visé** number and date, and attach its file if
    available.
3.  Add the invoice lines and check their taxes. For sales taxes mapped to
    **Tax Exemption**, the lines should show that 0% tax. On draft Tunisian
    invoices, changing the fiscal position in the form automatically updates
    existing line taxes and accounts. Check the taxes again before posting.
4.  Preview or print the invoice to see the attestation number and start
    date, along with the Bon de Commande Visé number and date.

The lookup uses the commercial partner, so an invoice addressed to a
child contact can use an attestation configured on its parent company.
If no attestation matches, the **Tax Exemption** field stays empty.
For Tunisian companies, the invoice uses the partner's configured fiscal
position in that case, or clears it if the partner has none. Changing the
partner or invoice date recalculates the attestation and fiscal position.
Check the fiscal position and invoice-line taxes before posting.

Changing countries re-evaluates exemption on draft documents. Certificates and
fiscal positions already recorded on posted documents are preserved.
