This module does not create a tax or a fiscal position. Set up the fiscal
position and the customer's attestation before creating an invoice:

1.  Go to *Accounting \> Configuration \> Fiscal Positions*. Open the
    Tunisian **Exemption** fiscal position, or create one for the company.
    Check that its **Tax Mapping** replaces the taxes used on invoices
    with the appropriate exempt taxes. The Tunisian chart includes a
    **0% Exemption** tax. A fiscal position needs at least one tax
    mapping to appear in the attestation's **Fiscal Position** field.
2.  Go to *Contacts* and open the customer's commercial partner. If
    invoices use a child contact, configure its parent company.
3.  On the **Invoicing** tab, under **Tax Exemptions**, add the
    **Attestation** number, **Start Date**, **End Date**, and **Fiscal
    Position**. Both dates are included in the validity period.

Avoid overlapping validity periods for the same partner: when more than
one attestation matches, the module selects only one of them.

If exemption must require a valid attestation, check that **Detect
Automatically** is disabled on the exemption fiscal position. Otherwise,
Odoo can apply that fiscal position even without an attestation.
