# Tunisian withholding tax (retenue à la source) — rules engine specification

This document describes a feature to be built for an Odoo deployment serving a Tunisian
client. It is written for a developer (or coding agent) who has not seen the earlier
design discussion. Read the whole thing before writing code — the accounting rules drive
the data model, and getting the model wrong here is expensive to undo.

---

## 1. Background: what retenue à la source is

Retenue à la source (RAS, "withholding at source") is a Tunisian tax mechanism. The
**payer** deducts a percentage of what it owes the **supplier**, pays the supplier the
net amount, and remits the withheld portion to the tax authority on the supplier's
behalf.

It is **not an extra charge**. It is an advance on the supplier's own income tax. The
payer must issue a _certificat de retenue à la source_ to the supplier, and that
document is what lets the supplier deduct the advance from their annual tax bill.
Without the certificate, the supplier effectively pays the tax twice.

The classic real-world confusion, which tells you exactly what the system does: a
merchant invoices 1,180 TND TTC to a company, receives 1,162 TND in their bank account,
and thinks it is a partial non-payment. In fact the client withheld 1.5% and remitted it
to the tax office.

### It is directional

The client sits on **both** sides of this and both must be supported:

- **As payer (on vendor bills):** the client withholds, pays net, remits the RAS to the
  State, and _issues_ the certificate. This is the legally obligated side. **Build this
  first.**
- **As supplier (on customer invoices):** the client's B2B customers withhold from
  _them_, pay net, and owe _them_ a certificate, which the client collects and uses as a
  tax credit.

### The single most important design constraint

**RAS is computed at payment, not at invoicing.** The threshold is also assessed per
payment, not per invoice.

Worked example that breaks any naive approach: the client has two invoices from the same
fabric supplier, 700.000 DT TTC each. Individually, each is below the 1,000 DT
threshold. But the rule tests the **payment**, not the invoice — so if the client
settles both in one payment of 1,400.000, RAS applies to the whole amount.

```
Payment total (2 invoices)     1 400.000
RAS 1.5% × 1 400.000        −     21.000
NET paid                       1 379.000
```

Consequences:

- You **cannot** model RAS as a negative tax line on the invoice. The invoice legally
  shows the full TTC amount — the customer's _debt_ is the full amount; only what is
  _paid_ is reduced.
- The trigger and the threshold are per payment, and a payment can span multiple
  invoices.
- The hook is at payment registration, not invoice confirmation.

There is a clean split that satisfies both the accounting reality and the UX goal:

| Moment                      | What happens                                                                                                                                             |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **On the bill / invoice**   | The rule determines _which_ withholding tax applies (nature, rate, accounts). No amount test yet. This is a computed suggestion, stored on the document. |
| **At payment registration** | The threshold is evaluated against the payment total, the amount is computed, and the journal entry is posted.                                           |

---

## 2. The feature being built

A configurable **rules table** that the user sets up once in Settings. Each row says:

> "If the document carries this article, apply this withholding tax."

Afterwards, every vendor bill and customer invoice is matched against the table
automatically. **The user never has to pick a withholding tax manually when registering
a payment.** If the document's article already has a rule, the tax is assigned for them.

That last sentence is the entire point of the feature. Optimise for it.

### The lookup, in one line

```
document → its article → matching rule → withholding tax → (at payment) amount computed
```

---

## 3. Data model

### 3.1 Cardinality — read this carefully

**Many articles map to one withholding tax.** This is a many-to-one relationship, not
one-to-one.

Example: the 10% rent withholding tax covers several distinct rental articles
(residential property rent, commercial premises rent, equipment rent, and so on). All of
them resolve to the same `account.tax` record. Conversely, a single article resolves to
exactly **one** withholding tax — otherwise the automatic match would be ambiguous and
the user would be back to choosing manually, which defeats the feature.

So:

- `withholding.article` → `withholding.rule` : one-to-one (each article has at most one
  rule)
- `withholding.rule` → `account.tax` : many-to-one (many rules share one tax)

### 3.2 Models

Use a module prefix appropriate to the project, e.g. `l10n_tn_withholding`. Model names
below are shown without the prefix for readability.

#### `withholding.article`

The catalogue of articles. This is **reference data** — ship a default set with the
module, but let the user add their own, because clients categorise their operations
differently.

| Field             | Type                         | Notes                                                                                                                              |
| ----------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `code`            | Char                         | Short unique code, e.g. `LOYER_IMM`. Useful for XML data ids and for the certificate.                                              |
| `name`            | Char, required, translatable | e.g. "Loyers d'immeubles"                                                                                                          |
| `description`     | Text                         | Full explanation of what falls under this article. Shown as a help text in the UI so the user understands what they are selecting. |
| `legal_reference` | Char                         | Optional. The Code IRPP/IS article reference, e.g. "Art. 52 §I". Prints on the certificate.                                        |
| `active`          | Boolean                      | Archive rather than delete.                                                                                                        |

#### `withholding.rule`

The rules table the user configures. **One row per article.**

| Field                | Type                                       | Notes                                                                                                                                           |
| -------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `article_id`         | Many2one → `withholding.article`, required | The matching key.                                                                                                                               |
| `description`        | Text, related or own field                 | Shown in the list so the user understands the row without opening it. Can be a `related` on the article's description, or an editable override. |
| `amount_min`         | Monetary, default `0.0`                    | The threshold, in TTC. `0` means "always applies". Set to `1000` where the law requires it.                                                     |
| `withholding_tax_id` | Many2one → `account.tax`, required         | Carries the rate and the accounts.                                                                                                              |
| `direction`          | Selection: `purchase` / `sale` / `both`    | Optional in v1 but recommended — the accounts differ per direction (see §6).                                                                    |
| `company_id`         | Many2one → `res.company`                   | Multi-company support.                                                                                                                          |
| `active`             | Boolean                                    | Archive rather than delete, so historical journal entries keep their link.                                                                      |

**SQL constraint:** `unique(article_id, company_id)` — one rule per article per company.
This is what guarantees an unambiguous automatic match.

#### Why two models instead of putting the rate on the article

You could collapse these into one model. Don't. Articles are _legal reference data_
shipped with the module and rarely edited; rules are _client configuration_ that the
accountant edits when the loi de finances changes. Keeping them separate means a module
upgrade can refresh the article catalogue without stomping the client's configured
rates.

#### `account.tax` — the withholding taxes

Do **not** store the rate on `withholding.rule`. Create one `account.tax` record per
distinct withholding rate and let the rule point at it. The tax carries:

- the percentage
- the account to book to (see §6 — different account per direction)
- a flag marking it as a withholding tax so it does not appear in normal tax pickers

Rationale: when a rate moves with the loi de finances, the accountant edits one tax
record and every rule pointing at it follows. Historical journal entries keep the tax
they were posted with. If the rate lived on the rule, you would have to edit every rule
and you would lose the audit trail.

#### `res.partner` extension

| Field                    | Type                             | Notes                          |
| ------------------------ | -------------------------------- | ------------------------------ |
| `withholding_article_id` | Many2one → `withholding.article` | The partner's default article. |

This is the field that makes the automation work in practice. A supplier is almost
always the same article every time: the landlord is always rent, the accountant is
always honoraires, the timber supplier is always goods. Set it once on the partner and
every future bill pre-fills.

#### `account.move` extension

| Field                    | Type                                            | Notes                                                                                                         |
| ------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `withholding_article_id` | Many2one → `withholding.article`                | Defaults from the partner. Editable — a supplier can occasionally bill something outside their usual article. |
| `withholding_rule_id`    | Many2one → `withholding.rule`, computed, stored | Resolved from the article. Stored so it survives configuration changes.                                       |
| `withholding_tax_id`     | Many2one → `account.tax`, related               | Convenience, read from the rule.                                                                              |

---

## 4. The matching logic

Deliberately simple. There is no scoring, no priority ordering, no wildcard fallback —
because `article_id` is unique per company, the lookup is a direct hit or a miss.

```python
def _compute_withholding_rule_id(self):
    for move in self:
        rule = False
        if move.withholding_article_id:
            rule = self.env['withholding.rule'].search([
                ('article_id', '=', move.withholding_article_id.id),
                ('company_id', '=', move.company_id.id),
            ], limit=1)
        move.withholding_rule_id = rule
```

**No match is a valid outcome.** If the article has no rule, or the document has no
article, no withholding applies. Do not raise an error and do not block the workflow —
plenty of bills legitimately carry no RAS.

### Where the article comes from

Priority order when creating a bill:

1. The article manually set on the bill (user override — always wins)
2. The partner's `withholding_article_id`
3. Nothing → no withholding

### Scope decision for v1: header-level, not line-level

Apply one article per document, on the header — not per invoice line.

Line-level matching is technically more correct (a bill could mix goods and services,
each with a different rate) but it roughly doubles the implementation cost and
complicates the payment-time computation considerably. Header-level covers the
overwhelming majority of real bills. Ship header-level, document the limitation, revisit
if the client hits it.

---

## 5. Payment-time behaviour

This is where the actual money moves. Extend the payment registration wizard
(`account.payment.register`) and `account.payment`.

Steps:

1. Gather the invoices/bills being settled by this payment.
2. Group them by `withholding_rule_id`. Documents with no rule are excluded from
   withholding.
3. For each group, sum the TTC amounts being paid.
4. Compare that sum against the rule's `amount_min`. **The comparison is against the
   payment total for that rule, not against each invoice individually** — this is the
   1,400 DT case from §1.
5. If the threshold is met, compute `withholding_amount = payment_total × tax_rate`.
6. Show the computed amount in the wizard, **editable**, so the accountant can override
   in edge cases. Show which rule and article produced it, so the number is never a
   black box.
7. Pay the supplier the net amount and post the withheld portion to the correct account.

### Currency precision

The company must be configured in **TND with 3 decimal places** (millimes). Tunisian
accounting expects millime precision. With 2-decimal rounding, 61.408 becomes 61.41 and
the figures will not reconcile against the client's real documents. Verify this before
testing any computation.

---

## 6. Accounting entries

The direction determines whether the withheld amount is an asset or a liability. This is
the cleanest way to hold the whole feature in your head.

### Purchase side — the client withholds from a supplier → LIABILITY

Buying wood for 5,951.000 TTC, RAS 1.5% = 89.265:

```
Dr  Fournisseur (401)              5 951.000
    Cr  Banque                              5 861.735
    Cr  RAS à reverser (liability)             89.265
```

The withheld portion parks as a liability the client remits to the tax office by the
28th of the following month. The client also issues the supplier a certificate.

### Sale side — a customer withholds from the client → ASSET

Selling office furniture for 11,901.000 TTC, the customer withholds 1.5% = 178.515:

```
Dr  Banque                       11 722.485
Dr  RAS à récupérer (asset)         178.515
    Cr  Client (411)                        11 901.000
```

The receivable clears in full; the withheld portion parks as a recoverable tax credit,
justified by the certificate the client receives from the customer.

**Summary: purchase side → `RAS à reverser` (liability); sale side → `RAS à récupérer`
(asset).** Two accounts, two directions, one payment-time mechanism.

---

## 7. Default data — the rules table

Ship these as default records. **Treat every rate as provisional** — see §9.

| Article                           | Description                                                                                          | Amount (TTC) | Withholding tax               |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------ | ----------------------------- |
| Acquisitions de biens et services | Achats de marchandises, matériel, équipements et services auprès d'un fournisseur local              | 1 000        | RAS Acquisitions 1,5 %        |
| Acquisitions — taux réduit        | Ventes aux entreprises totalement exportatrices, ou fournisseur à carte fiscale valide               | 1 000        | RAS Acquisitions réduit 0,5 % |
| Loyers                            | Loyers d'immeubles et de matériel versés au bailleur                                                 | 0            | RAS Loyers 10 %               |
| Honoraires et commissions         | Honoraires, commissions, courtages et rémunérations non commerciales                                 | 0            | RAS Honoraires 10 %           |
| Honoraires — taux réduit          | Honoraires versés à une société soumise à l'IS ou à un régime réel tenant une comptabilité régulière | 0            | RAS Honoraires réduit 3 %     |
| Marchés publics                   | Montants payés dans le cadre d'un marché conclu avec l'État ou une entité publique                   | 1 000        | RAS Marchés publics 3 %       |
| Redevances et capitaux mobiliers  | Redevances, droits d'auteur et revenus de capitaux mobiliers                                         | 0            | RAS Redevances 15 %           |
| Paiements aux non-résidents       | Sommes payées à un bénéficiaire non résident, sauf taux réduit prévu par une convention fiscale      | 0            | RAS Non-résidents 15 %        |
| TVA retenue par l'État            | Retenue sur la TVA facturée, applicable aux acquisitions de l'État et des entités publiques          | 1 000        | RAS TVA 25 % de la TVA        |

Notes on this table:

- The **reduced-rate variants are separate articles**, not conditions on a single
  article. This is what keeps the lookup unambiguous. The user selects "Honoraires —
  taux réduit" when the supplier is an IS company, and that choice sticks on the partner
  record.
- **Loyers is split out from honoraires.** The source law text bundles them at the same
  10% rate, but users think of rent as its own thing and will look for it by name.
- **The last row does not compute like the others.** Every other rate applies to the
  document total; the 25% applies to the TVA amount only. Either give its tax record a
  different base, or mark it out of scope for v1. It only concerns clients selling to
  the State.
- Several articles will share a tax as the catalogue grows — e.g. adding "Loyers de
  matériel" and "Loyers commerciaux" as separate articles, both pointing at RAS Loyers
  10 %. The model supports this by design.

---

## 8. Settings UI

Put the rules table in the accounting Settings, under a Tunisia / Localisation section.

- An editable list view of `withholding.rule` with columns: Article, Description,
  Amount, Withholding tax. Inline editable — the accountant should be able to change a
  threshold without opening a form.
- A separate menu for `withholding.article` so the catalogue can be extended.
- A boolean setting to enable/disable the whole feature.

The `withholding_article_id` field on the partner form should sit in the Accounting tab,
near the fiscal position, with a tooltip explaining that it drives automatic
withholding.

---

## 9. Caveats and open questions

**Verify every rate before go-live.** RAS rates and thresholds move with each annual loi
de finances, and the rates above come from a design discussion, not from a current
reading of the Code IRPP/IS. The loyers rate in particular varies across sources. The
client's expert-comptable must sign off on the default data.

**No official `l10n_tn` exists.** Tunisia is not an officially supported Odoo fiscal
localisation, so none of this is wired up for you. Existing solutions are closed
products sold by local IT firms.

**Related features, out of scope for this document:** the _certificat de retenue à la
source_ as a QWeb report (needs both parties' matricule fiscal, nature, base, rate,
amount, period), and the TEJ XML export for the monthly declaration. Since January 2026
all Tunisian companies must declare withholding through the TEJ platform in XML format.
Both are separate mini-projects that depend on this rules engine but should not be built
into it.

**Odoo version matters.** Newer Odoo versions ship more payment-level withholding
machinery that this could lean on instead of being rolled fully custom. Check what the
target version offers before writing the payment hook from scratch.
