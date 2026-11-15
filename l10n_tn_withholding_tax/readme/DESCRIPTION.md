This module adds Tunisian withholding tax (*retenue à la source*)
handling on bill payments.

It does **not** create any journal or rule of its own. Instead, it lets
you flag bank journals as withholding tax journals, each with its own
rate, and define **Withholding Rules** that link products to one of
these journals, or apply based only on a minimum invoice total when
no products are selected.

When you register a payment on a bill with an applicable rule, the
payment wizard:

- shows the applicable withholding taxes and the amount to withhold for
  each one;
- hides the withholding tax journals that do not apply to the bill;
- fills in the withholding amount when you select one of the applicable
  journals.

The withholding amount is computed on the bill total, taxes included,
and is recorded as a payment in the withholding tax journal. Once a
withholding tax has been paid on a bill, it is no longer proposed for
that bill.
