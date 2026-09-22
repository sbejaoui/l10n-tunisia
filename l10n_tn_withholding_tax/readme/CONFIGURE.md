This module does not create any journal or rule. You set them up in two
steps.

**Withholding tax journals**

1.  Go to *Accounting \> Configuration \> Journals*.
2.  Create (or open) a journal of type **Bank**. Use one journal per
    withholding tax rate.
3.  Open the **Advanced Settings** tab and, in the **Withholding Tax**
    section, tick **Journal includes Withholding Tax**.
4.  Set the **Rate** of the withholding tax.

The **Withholding Tax** section is only shown on journals of type
**Bank**.

**Withholding rules**

1.  Go to *Accounting \> Configuration \> Withholding Rules*.
2.  Create a rule and fill in:
    - **Article**: the product the rule applies to.
    - **Description**: a short explanation of the rule.
    - **Amount**: the minimum bill total (taxes included) from which the
      withholding applies. Use 0 to apply it to every bill. This amount
      cannot be negative.
    - **Withholding Tax Journal**: the journal holding the rate to
      apply. Only journals with **Journal includes Withholding Tax**
      ticked can be selected.
