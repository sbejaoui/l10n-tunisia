Once the journals and rules are configured (see *Configuration*), the
withholding tax is handled from the payment wizard:

1.  Open a posted vendor bill that meets a withholding rule's conditions,
    and click **Pay**.
2.  At the top of the wizard, a message lists the applicable withholding
    taxes, with the journal and the amount to withhold for each one.
3.  In **Journal**, select the withholding tax journal. The **Amount** is
    filled in automatically with the withholding amount.
4.  Click **Create Payment**.
5.  Pay the rest of the bill as usual with your bank journal.

A rule applies when the bill total is equal to or higher than the rule's
**Amount** and, if products are selected, the bill contains one of them.
Rules without products also apply to invoice lines without a product.
Amount-only and matching product rules can both apply. Withholding tax journals
that do not match an applicable rule are not offered in the **Journal**
field.

Once the withholding tax has been paid, its journal is no longer offered
for that bill and the rule no longer appears in the wizard.
