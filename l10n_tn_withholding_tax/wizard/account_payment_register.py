# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    withholding_tax_alert = fields.Text(compute="_compute_withholding_tax_alert")
    has_multiple_bills = fields.Boolean(compute="_compute_has_multiple_bills")
    multiple_bills_alert = fields.Text(compute="_compute_multiple_bills_alert")
    withholding_journal_selected = fields.Boolean()
    show_withholding_tax_applicable = fields.Boolean(
        compute="_compute_show_withholding_tax_applicable",
    )
    withholding_tax_applicable = fields.Boolean()
    withholding_handling = fields.Selection(
        [("keep_unpaid", "Keep Unpaid"), ("pay", "Register Withholding Payment")],
        default="keep_unpaid",
    )
    withholding_allocation_line_ids = fields.One2many(
        "l10n_tn.payment.register.withholding.line",
        "wizard_id",
        compute="_compute_withholding_allocation_line_ids",
        store=True,
        readonly=False,
        copy=False,
    )
    withholding_allocation_warning = fields.Text(
        compute="_compute_withholding_allocation_warning",
    )

    @api.onchange("journal_id")
    def _calculate_withholding_amount(self):
        if self.journal_id.is_withholding_tax_journal:
            eligible_bills = self._get_withholding_eligible_bills()
            total_amount = sum(bill.amount_total for bill in eligible_bills)
            withholding_amount = total_amount * self.journal_id.withholding_tax_rate
            self.amount = withholding_amount
            self.withholding_journal_selected = True
        elif self.journal_id and self.withholding_journal_selected:
            self.withholding_journal_selected = False
            self.custom_user_amount = False
            self.custom_user_currency_id = False
            self._compute_amount()

    @api.depends(
        "line_ids",
        "line_ids.move_id.l10n_tn_is_domestic_transaction",
        "line_ids.move_id.line_ids.matched_debit_ids",
        "line_ids.move_id.line_ids.matched_credit_ids",
        "line_ids.move_id.move_type",
        "line_ids.move_id.company_id",
        "line_ids.move_id.amount_total",
        "line_ids.move_id.invoice_line_ids.product_id",
        "line_ids.move_id.currency_id",
    )
    def _compute_withholding_tax_alert(self):
        for record in self:
            invoices = record.line_ids.move_id
            currency = invoices.currency_id
            if len(currency) > 1:
                record.withholding_tax_alert = self.env._(
                    "Register withholding separately for invoices "
                    "in different currencies."
                )
                continue
            rules = self.env["l10n.tn.withholding.rule"]._get_applicable_rules(invoices)

            if rules:
                message = self.env._("Applicable withholding rules:\n")
                for rule in rules:
                    eligible_bills = invoices.filtered(
                        lambda bill, bound_rule=rule: (
                            bound_rule
                            in self.env[
                                "l10n.tn.withholding.rule"
                            ]._get_applicable_rules(bill)
                        )
                    )

                    amount = rule._get_withholding_amount(eligible_bills)
                    net_amount = rule._get_net_amount(eligible_bills)
                    formatted_net = formatLang(
                        self.env, net_amount, currency_obj=currency
                    )
                    message += rule._get_withholding_alert_message(
                        amount, currency, eligible_bills
                    )
                    message += self.env._(
                        "  Amount after withholding: %(amount)s\n",
                        amount=formatted_net,
                    )
                record.withholding_tax_alert = message
            else:
                record.withholding_tax_alert = False

    @api.depends("line_ids")
    def _compute_has_multiple_bills(self):
        for record in self:
            record.has_multiple_bills = len(record.line_ids.move_id) > 1

    @api.depends("journal_id", "has_multiple_bills")
    def _compute_multiple_bills_alert(self):
        for record in self:
            if (
                record.journal_id.is_withholding_tax_journal
                and record.has_multiple_bills
            ):
                record.multiple_bills_alert = self.env._(
                    "You are about to pay the withholding tax of multiple bills."
                )
            else:
                record.multiple_bills_alert = False

    @api.onchange("journal_id")
    def _check_withholding_tax_already_paid(self):
        if not self.journal_id.is_withholding_tax_journal:
            return

        payments = self.line_ids.move_id.mapped(
            lambda invoice: invoice._get_reconciled_withholding_payments()
        )

        if any(
            payment.journal_id == self.journal_id
            and payment.state in ("in_process", "paid")
            for payment in payments
        ):
            raise UserError(self.env._("This withholding tax has already been paid."))

    def _create_payments(self):
        self.ensure_one()

        if self.withholding_tax_applicable:
            return self._create_allocated_payments()

        if not self.journal_id.is_withholding_tax_journal:
            return super()._create_payments()

        if len(self.line_ids.move_id.currency_id) > 1:
            raise UserError(
                self.env._(
                    "Register withholding separately for invoices "
                    "in different currencies."
                )
            )

        eligible_bills = self._get_withholding_eligible_bills()
        if not eligible_bills:
            raise UserError(
                self.env._("No selected bill is eligible for this withholding journal.")
            )

        if not self.has_multiple_bills:
            return super()._create_payments()

        payments = self.env["account.payment"]
        for bill in eligible_bills:
            payment_wizard = (
                self.env["account.payment.register"]
                .with_context(
                    active_model="account.move",
                    active_ids=[bill.id],
                )
                .create({})
            )

            payment_wizard.journal_id = self.journal_id
            payment_wizard.payment_date = self.payment_date
            payment_wizard.payment_method_line_id = self.payment_method_line_id
            payment_wizard._calculate_withholding_amount()

            payments |= payment_wizard._create_payments()

        return payments

    @api.depends(
        "payment_type",
        "company_id",
        "can_edit_wizard",
        "line_ids.move_id.l10n_tn_is_domestic_transaction",
        "line_ids.move_id.line_ids.matched_debit_ids",
        "line_ids.move_id.line_ids.matched_credit_ids",
        "line_ids.move_id.move_type",
        "line_ids.move_id.company_id",
        "line_ids.move_id.amount_total",
        "line_ids.move_id.invoice_line_ids.product_id",
        "withholding_tax_applicable",
        "line_ids.move_id.currency_id",
    )
    def _compute_available_journal_ids(self):
        res = super()._compute_available_journal_ids()
        for wizard in self:
            invoices = wizard.line_ids.move_id
            rules = self.env["l10n.tn.withholding.rule"]._get_applicable_rules(invoices)
            wizard.available_journal_ids = (
                wizard.available_journal_ids.filtered(
                    lambda j: not j.is_withholding_tax_journal
                )
                + rules.withholding_journal_id
            )
            if wizard.withholding_tax_applicable or len(invoices.currency_id) > 1:
                wizard.available_journal_ids = wizard.available_journal_ids.filtered(
                    lambda journal: not journal.is_withholding_tax_journal
                )

        return res

    def _get_withholding_eligible_bills(self):
        self.ensure_one()
        rules = self.env["l10n.tn.withholding.rule"]

        return self.line_ids.move_id.filtered(
            lambda bill: (
                self.journal_id
                in rules._get_applicable_rules(bill).withholding_journal_id
            )
        )

    @api.depends(
        "line_ids",
        "line_ids.move_id.l10n_tn_is_domestic_transaction",
        "line_ids.move_id.line_ids.matched_debit_ids",
        "line_ids.move_id.line_ids.matched_credit_ids",
        "line_ids.move_id.move_type",
        "line_ids.move_id.company_id",
        "line_ids.move_id.amount_total",
        "line_ids.move_id.invoice_line_ids.product_id",
        "line_ids.move_id.matched_payment_ids.state",
        "line_ids.move_id.currency_id",
    )
    def _compute_show_withholding_tax_applicable(self):
        rules = self.env["l10n.tn.withholding.rule"]
        for wizard in self:
            invoices = wizard.line_ids.move_id
            wizard.show_withholding_tax_applicable = (
                len(invoices) > 1
                and len(invoices.currency_id) == 1
                and bool(rules._get_applicable_rules(invoices))
            )

    @api.depends(
        "line_ids",
        "line_ids.move_id.move_type",
        "line_ids.move_id.company_id",
        "line_ids.move_id.amount_total",
        "line_ids.move_id.invoice_line_ids.product_id",
        "line_ids.move_id.l10n_tn_is_domestic_transaction",
        "line_ids.move_id.line_ids.matched_debit_ids",
        "line_ids.move_id.line_ids.matched_credit_ids",
        "withholding_tax_applicable",
    )
    def _compute_withholding_allocation_line_ids(self):
        rules = self.env["l10n.tn.withholding.rule"]
        for wizard in self:
            commands = [Command.clear()]
            if wizard.withholding_tax_applicable:
                for invoice in wizard.line_ids.move_id.sorted("id"):
                    journals = rules._get_applicable_rules(
                        invoice
                    ).withholding_journal_id
                    commands.append(
                        Command.create(
                            {
                                "invoice_id": invoice.id,
                                "invoice_balance": invoice.amount_residual,
                                "withholding_journal_ids": [Command.set(journals.ids)],
                            }
                        )
                    )
            wizard.withholding_allocation_line_ids = commands

    @api.onchange("withholding_tax_applicable", "withholding_allocation_line_ids")
    def _onchange_withholding_allocation(self):
        if self.withholding_tax_applicable:
            amount = sum(self.withholding_allocation_line_ids.mapped("cash_amount"))
            self.custom_user_amount = amount
            self.custom_user_currency_id = self.currency_id
            self.group_payment = True
            self.installments_mode = "full"
            self.payment_difference_handling = "open"
            self.amount = amount
        else:
            self.custom_user_amount = False
            self.custom_user_currency_id = False
            self._compute_amount()

    @api.depends("withholding_tax_applicable")
    def _compute_amount(self):
        allocated = self.filtered("withholding_tax_applicable")
        result = super(AccountPaymentRegister, self - allocated)._compute_amount()
        for wizard in allocated:
            # changing journals or installments must not restore the gross amount
            wizard.amount = wizard.amount
        return result

    @api.onchange("amount")
    def _onchange_amount(self):
        result = super()._onchange_amount()
        if (
            not self.withholding_tax_applicable
            or not self.currency_id
            or self.currency_id != self.company_currency_id
        ):
            return result
        lines = self.withholding_allocation_line_ids
        currency = self.currency_id
        # a table edit already defines its own distribution, do not replace it
        if currency.is_zero(self.amount - sum(lines.mapped("cash_amount"))):
            return result
        remaining_net = sum(
            max(line.invoice_balance - line.withholding_amount, 0) for line in lines
        )
        if (
            currency.compare_amounts(self.amount, 0) < 0
            or currency.compare_amounts(self.amount, remaining_net) > 0
        ):
            return result
        remaining = currency.round(self.amount)
        for line in lines:
            capacity = max(line.invoice_balance - line.withholding_amount, 0)
            allocation = min(capacity, remaining)
            line.cash_amount = allocation
            remaining = currency.round(remaining - allocation)
        return result

    @api.depends("withholding_tax_applicable")
    def _compute_payment_difference_handling(self):
        result = super()._compute_payment_difference_handling()
        self.filtered("withholding_tax_applicable").payment_difference_handling = "open"
        return result

    def _get_withholding_allocation_errors(self):
        self.ensure_one()
        errors = []
        invoices = self.line_ids.move_id
        allocations = self.withholding_allocation_line_ids
        currency = self.currency_id
        if (
            len(invoices) < 2
            or len(self.batches) != 1
            or len(invoices.company_id) != 1
            or invoices.company_id != self.company_id
            or len(self.line_ids.account_id) != 1
            or len(set(invoices.mapped("move_type"))) != 1
            or any(
                move.move_type not in ("out_invoice", "in_invoice") for move in invoices
            )
        ):
            errors.append(
                self.env._(
                    "Select at least two invoices for one partner, company and "
                    "receivable/payable account, without mixing invoices and refunds."
                )
            )
        if (
            currency != self.company_currency_id
            or invoices.currency_id != self.company_currency_id
        ):
            errors.append(
                self.env._("Invoice allocations require the company currency.")
            )
        if (
            self.journal_id.type not in ("bank", "cash")
            or self.journal_id.is_withholding_tax_journal
        ):
            errors.append(self.env._("Select a regular bank or cash journal."))
        if self.withholding_handling not in ("pay", "keep_unpaid"):
            errors.append(self.env._("Choose how to handle withholding."))
        if set(allocations.invoice_id.ids) != set(invoices.ids) or len(
            allocations
        ) != len(invoices):
            errors.append(self.env._("Provide exactly one allocation per invoice."))
        if currency.compare_amounts(self.amount, 0) <= 0:
            errors.append(
                self.env._("The bank/cash payment must be greater than zero.")
            )
        if not currency.is_zero(self.amount - sum(allocations.mapped("cash_amount"))):
            errors.append(
                self.env._("Cash allocations must total the bank/cash payment amount.")
            )
        rules = self.env["l10n.tn.withholding.rule"]
        for line in allocations:
            invoice = line.invoice_id
            journals = rules._get_applicable_rules(invoice).withholding_journal_id
            # onchange x2many records have virtual ids, compare their database origins
            selected_journals = line.withholding_journal_ids._origin
            if selected_journals - journals or any(
                journal.company_id != self.company_id
                or not journal.is_withholding_tax_journal
                or not 0 < journal.withholding_tax_rate <= 1
                for journal in selected_journals
            ):
                errors.append(
                    self.env._(
                        "The withholding journals or rates for %(invoice)s "
                        "do not match its applicable rules.",
                        invoice=invoice.display_name,
                    )
                )
            if invoice.state != "posted" or not currency.is_zero(
                invoice.amount_residual - line.invoice_balance
            ):
                errors.append(
                    self.env._(
                        "The balance of %(invoice)s changed. "
                        "Reopen the payment wizard.",
                        invoice=invoice.display_name,
                    )
                )
            if (
                currency.compare_amounts(line.cash_amount, 0) < 0
                or currency.compare_amounts(line.withholding_amount, 0) < 0
                or currency.compare_amounts(
                    line.cash_amount + line.withholding_amount, line.invoice_balance
                )
                > 0
            ):
                errors.append(
                    self.env._(
                        "Cash plus withholding cannot exceed the balance of "
                        "%(invoice)s, and amounts cannot be negative.",
                        invoice=invoice.display_name,
                    )
                )
        return errors

    @api.depends(
        "withholding_tax_applicable",
        "withholding_handling",
        "amount",
        "currency_id",
        "journal_id",
        "withholding_allocation_line_ids.cash_amount",
        "withholding_allocation_line_ids.withholding_amount",
        "withholding_allocation_line_ids.invoice_id.amount_residual",
    )
    def _compute_withholding_allocation_warning(self):
        for wizard in self:
            messages = []
            if wizard.withholding_tax_applicable:
                messages = wizard._get_withholding_allocation_errors()
                if not wizard.withholding_allocation_line_ids.withholding_journal_ids:
                    messages.append(
                        self.env._(
                            "No withholding journals are selected. "
                            "No withholding will be reserved or registered."
                        )
                    )
                net = sum(
                    line.invoice_balance - line.withholding_amount
                    for line in wizard.withholding_allocation_line_ids
                )
                if not wizard.currency_id.is_zero(wizard.amount - net):
                    messages.append(
                        self.env._(
                            "The suggested net payment is %(net)s. A partial payment "
                            "is allowed if its cash allocations match "
                            "the amount received.",
                            net=formatLang(
                                self.env, net, currency_obj=wizard.currency_id
                            ),
                        )
                    )
            wizard.withholding_allocation_warning = "\n".join(messages) or False

    def _create_allocated_payments(self):
        self.ensure_one()
        self.custom_user_amount = self.amount
        self.custom_user_currency_id = self.currency_id
        errors = self._get_withholding_allocation_errors()
        if errors:
            raise UserError("\n".join(errors))
        self.group_payment = True
        self.installments_mode = "full"
        self.payment_difference_handling = "open"
        payments = super()._create_payments()
        if len(payments) != 1:
            raise UserError(
                self.env._("Invoice allocations require one bank/cash payment.")
            )
        if self.withholding_handling == "pay":
            for line in self.withholding_allocation_line_ids:
                for journal, amount in line._get_withholding_amounts():
                    if self.currency_id.is_zero(amount):
                        continue
                    withholding_wizard = (
                        self.env["account.payment.register"]
                        .with_context(
                            active_model="account.move",
                            active_ids=line.invoice_id.ids,
                        )
                        .create({})
                    )
                    withholding_wizard.journal_id = journal
                    withholding_wizard.payment_date = self.payment_date
                    withholding_wizard.custom_user_amount = amount
                    withholding_wizard.custom_user_currency_id = self.currency_id
                    withholding_wizard.amount = amount
                    withholding_wizard.payment_difference_handling = "open"
                    withholding_wizard._create_payments()
        return payments

    def _init_payments(self, to_process, edit_mode=False):
        payments = super()._init_payments(to_process, edit_mode=edit_mode)
        if (
            self.withholding_tax_applicable
            or self.journal_id.is_withholding_tax_journal
        ):
            for payment in payments.filtered(lambda payment: not payment.move_id):
                if not payment.outstanding_account_id:
                    payment.outstanding_account_id = payment._get_outstanding_account(
                        payment.payment_type
                    )
                payment._generate_journal_entry()
        return payments

    def _reconcile_payments(self, to_process, edit_mode=False):
        if not self.withholding_tax_applicable:
            return super()._reconcile_payments(to_process, edit_mode=edit_mode)
        for values in to_process:
            payment = values["payment"]
            _liquidity, counterpart, _writeoff = payment._seek_for_lines()
            if len(counterpart) != 1:
                raise UserError(
                    self.env._("Expected one payment counterpart journal item.")
                )
            for allocation in self.withholding_allocation_line_ids:
                if self.currency_id.is_zero(allocation.cash_amount):
                    continue
                invoice_lines = values["to_reconcile"].filtered(
                    lambda aml, a=allocation: (
                        aml.move_id == a.invoice_id and not aml.reconciled
                    )
                )
                (counterpart + invoice_lines).with_context(
                    l10n_tn_payment_allocation=(counterpart.id, allocation.cash_amount)
                ).reconcile()
                allocation.invoice_id.matched_payment_ids += payment
            if not counterpart.reconciled:
                raise UserError(
                    self.env._(
                        "The payment could not be allocated in full. Reopen the wizard."
                    )
                )
        return None
