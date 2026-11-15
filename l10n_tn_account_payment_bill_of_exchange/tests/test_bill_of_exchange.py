# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
import base64
import json
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged
from odoo.tools import file_open

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestBillOfExchange(AccountTestInvoicingCommon):
    chart_template = "tn"
    country_code = "TN"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chart = cls.env["account.chart.template"]
        cls.bill_method = cls.chart.ref("tn_boe_inbound")
        cls.cash_journal = cls.env["account.journal"].create(
            {
                "name": "Bills test cash",
                "code": "BTCS",
                "type": "cash",
            }
        )
        cls.cash_method = cls.cash_journal.inbound_payment_method_line_ids.filtered(
            lambda method: method.code == "manual"
        )[:1]
        cls.cash_method.payment_account_id = cls.cash_journal.default_account_id
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.bank_method = cls.bank_journal.inbound_payment_method_line_ids.filtered(
            lambda method: method.code == "manual"
        )[:1]
        cls.bank_outstanding = cls.env["account.account"].create(
            {
                "name": "Bills test bank receipts",
                "code": "589998",
                "account_type": "asset_current",
                "reconcile": True,
                "company_ids": [Command.set(cls.env.company.ids)],
            }
        )
        cls.bank_method.payment_account_id = cls.bank_outstanding
        cls.proof = base64.b64encode(b"signed test evidence")

    def setUp(self):
        super().setUp()
        self.reference_number = 0
        self.today = fields.Date.today()

    def _invoice(self, amount=1000):
        return self.init_invoice(
            "out_invoice",
            partner=self.partner_a,
            amounts=[amount],
            taxes=[],
            invoice_date=self.today,
            post=True,
        )

    def _bill(self, invoices, amount=None, post=True, **extra):
        self.reference_number += 1
        values = {
            "partner_id": invoices.commercial_partner_id.id,
            "amount": amount
            if amount is not None
            else sum(invoices.mapped("amount_residual")),
            "payment_type": "inbound",
            "partner_type": "customer",
            "journal_id": self.bill_method.journal_id.id,
            "payment_method_line_id": self.bill_method.id,
            "currency_id": self.env.ref("base.TND").id,
            "date": self.today,
            "boe_reference": f"BILL-{self.reference_number}",
            "boe_issue_date": self.today,
            "boe_maturity_date": self.today + timedelta(days=30),
            "boe_received_date": self.today,
            "boe_acceptance": "accepted",
            "boe_acceptance_date": self.today,
            "boe_signed_document": self.proof,
            "boe_signed_filename": "signed.pdf",
            "boe_invoice_ids": [Command.set(invoices.ids)],
        }
        values.update(extra)
        bill = self.env["account.payment"].create(values)
        if post:
            bill.action_post()
        return bill

    def _operation(self, bill, operation, amount=0, **extra):
        values = {
            "bill_id": bill.id,
            "operation": operation,
            "amount": amount,
            "date": self.today,
            "reference": f"Operation {operation}",
        }
        values.update(extra)
        wizard = self.env["l10n_tn.boe.operation"].create(values)
        wizard.action_apply()
        return wizard

    def _collect(self, bill, amount, bank=False, incident=None, **extra):
        journal = self.bank_journal if bank else self.cash_journal
        method = self.bank_method if bank else self.cash_method
        operation = "recover" if incident else "collect"
        self._operation(
            bill,
            operation,
            amount,
            journal_id=journal.id,
            payment_method_line_id=method.id,
            incident_id=incident.id if incident else False,
            **extra,
        )
        return bill.boe_settlement_ids.sorted("id")[-1]

    def _unpaid(self, bill, amount):
        self._operation(
            bill,
            "unpaid",
            amount,
            journal_id=self.chart.ref("general").id,
            reason="Debtor did not pay",
            document=self.proof,
        )
        return bill.boe_incident_ids.sorted("id")[-1]

    def _bank_match(self, collection):
        statement = self.env["account.bank.statement.line"].create(
            {
                "journal_id": self.bank_journal.id,
                "amount": collection.payment_id.amount,
                "date": self.today,
                "payment_ref": collection.reference,
                "partner_id": self.partner_a.id,
            }
        )
        _liquidity, suspense, _other = statement._seek_for_lines()
        suspense.with_context(skip_account_move_synchronization=True).write(
            {
                "account_id": collection.payment_id.outstanding_account_id.id,
                "partner_id": self.partner_a.id,
            }
        )
        (suspense + collection.payment_id._seek_for_lines()[0]).reconcile()
        return statement

    def test_partial_invoice_coverage(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 600)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(bill.boe_collected_amount, 0)
        self.assertEqual(bill.state, "in_process")
        self.assertEqual(
            bill._seek_for_lines()[0].date_maturity, bill.boe_maturity_date
        )

    def test_receipt_and_collection_keep_principal(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        self.assertEqual(sum(bill.move_id.line_ids.mapped("debit")), 600)
        collection = self._collect(bill, 200)
        self.assertEqual(
            sum(collection.payment_id.move_id.line_ids.mapped("debit")), 200
        )

    def test_full_coverage_stays_in_payment(self):
        invoice = self._invoice()
        bill = self._bill(invoice)
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(invoice.payment_state, "in_payment")
        self.assertFalse(bill.is_matched)
        self.assertEqual(bill.state, "in_process")
        self._collect(bill, 200)
        self.assertEqual(invoice.payment_state, "in_payment")
        self.assertEqual(bill.state, "in_process")
        self.assertEqual(bill.boe_active_amount, bill.amount - 200)
        self._collect(bill, bill.amount - 200)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(bill.boe_active_amount, 0)
        self.assertEqual(bill.state, "paid")

    def test_register_payment_wizard_uses_native_entry_and_allocation(self):
        invoice = self._invoice()
        wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create(
                {
                    "journal_id": self.bill_method.journal_id.id,
                    "payment_method_line_id": self.bill_method.id,
                    "amount": 600,
                    "payment_difference_handling": "open",
                    "boe_reference": "FROM-WIZARD",
                    "boe_issue_date": self.today,
                    "boe_maturity_date": self.today + timedelta(days=30),
                    "boe_received_date": self.today,
                    "boe_acceptance_date": self.today,
                    "boe_signed_document": self.proof,
                }
            )
        )
        bill = wizard._create_payments()
        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.move_id.state, "posted")
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 600)

    def test_bill_wizard_groups_invoices_and_allows_partial_amount(self):
        invoices = self._invoice(700) | self._invoice(500)
        wizard_form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=invoices.ids
            )
        )
        wizard_form.journal_id = self.bank_journal
        wizard_form.payment_method_line_id = self.bank_method
        self.assertFalse(wizard_form.group_payment)
        wizard_form.journal_id = self.bill_method.journal_id
        wizard_form.payment_method_line_id = self.bill_method
        self.assertTrue(wizard_form.group_payment)
        wizard_form.amount = 1000
        wizard_form.payment_difference_handling = "open"
        wizard_form.boe_reference = "MULTI-FROM-WIZARD"
        wizard_form.boe_maturity_date = self.today + timedelta(days=30)
        wizard_form.boe_signed_document = self.proof
        wizard = wizard_form.save()
        self.assertTrue(wizard.group_payment)
        self.assertEqual(wizard.amount, 1000)
        bill = wizard._create_payments()
        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.amount, 1000)
        self.assertEqual(set(bill.boe_invoice_ids.ids), set(invoices.ids))
        self.assertEqual(bill.boe_active_amount, 1000)
        self.assertEqual(sum(invoices.mapped("amount_residual")), 200)

    def test_bill_wizard_does_not_group_incompatible_customers(self):
        invoices = self._invoice(700) | self.init_invoice(
            "out_invoice",
            partner=self.partner_b,
            amounts=[500],
            taxes=[],
            invoice_date=self.today,
            post=True,
        )
        wizard_form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=invoices.ids
            )
        )
        wizard_form.journal_id = self.bill_method.journal_id
        wizard_form.payment_method_line_id = self.bill_method
        self.assertFalse(wizard_form.can_edit_wizard)
        self.assertFalse(wizard_form.group_payment)

    def test_bill_record_rules_isolate_companies(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        other = self.setup_other_company()["company"]
        other_method = (
            self.env["account.chart.template"].with_company(other).ref("tn_boe_inbound")
        )
        foreign = (
            self.env["account.payment"]
            .with_company(other)
            .create(
                {
                    "company_id": other.id,
                    "journal_id": other_method.journal_id.id,
                    "payment_method_line_id": other_method.id,
                    "partner_id": self.partner_a.id,
                    "amount": 600,
                    "currency_id": other.currency_id.id,
                    "boe_reference": "FOREIGN",
                }
            )
        )
        self.assertEqual(
            foreign.destination_account_id,
            self.partner_a.with_company(other).property_account_receivable_id,
        )
        reader = new_test_user(
            self.env,
            login="bill_single_company",
            groups="account.group_account_readonly",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        visible = (
            self.env["account.payment"]
            .with_user(reader)
            .with_context(
                allowed_company_ids=self.env.company.ids,
            )
            .search([("tn_boe", "=", True)])
        )
        self.assertIn(bill, visible)
        self.assertNotIn(foreign, visible)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            foreign.with_user(reader).read(["boe_reference"])

    def test_draft_and_missing_acceptance(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600, post=False, boe_acceptance="pending")
        self.assertEqual(invoice.amount_residual, invoice.amount_total)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            bill.action_post()
        self.assertFalse(bill.move_id)

    def test_multi_invoice_and_multiple_bills(self):
        invoices = self._invoice(700) | self._invoice(500)
        bill = self._bill(invoices, 1000)
        self.assertEqual(
            sum(invoices.mapped("amount_residual")),
            sum(invoices.mapped("amount_total")) - 1000,
        )
        self.assertEqual(bill.boe_active_amount, 1000)
        self.assertEqual(len(bill.boe_invoice_ids), 2)
        second = self._bill(invoices, 100)
        self.assertEqual(second.boe_active_amount, 100)

    def test_cash_collection_does_not_credit_invoice_twice(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        before = invoice.amount_residual
        collection = self._collect(bill, 200)
        self.assertEqual(collection.state, "confirmed")
        self.assertEqual(
            collection.payment_id.destination_account_id, bill.outstanding_account_id
        )
        self.assertEqual(invoice.amount_residual, before)
        self.assertEqual(bill.boe_active_amount, 400)
        self.assertEqual(bill.boe_collected_amount, 200)

    def test_pending_bank_payment_and_confirmation(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        collection = self._collect(bill, 200, bank=True)
        self.assertEqual(
            collection.payment_id.outstanding_account_id, self.bank_outstanding
        )
        self.assertEqual(collection.state, "pending")
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(bill.boe_pending_amount, 200)
        self.assertEqual(bill.boe_available_amount, 400)
        self._bank_match(collection)
        collection.action_confirm()
        self.assertEqual(bill.boe_active_amount, 400)
        self.assertEqual(bill.boe_pending_amount, 0)

    def test_manual_bank_collection_confirmation(self):
        for configured in (True, False):
            with self.subTest(configured=configured):
                self.bank_method.payment_account_id = (
                    self.bank_outstanding if configured else False
                )
                invoice = self._invoice()
                bill = self._bill(invoice)
                collection = self._collect(bill, 200, bank=True)
                self.assertEqual(collection.state, "pending")
                self.assertTrue(collection.ready_to_confirm)
                self.assertFalse(collection.payment_id.is_matched)
                collection.action_confirm()
                self.assertEqual(collection.state, "confirmed")
                self.assertEqual(collection.payment_id.state, "paid")
                self.assertFalse(collection.payment_id.is_matched)
                self.assertEqual(bill.boe_active_amount, bill.amount - 200)
                self.assertEqual(bill.boe_pending_amount, 0)
                self.assertEqual(bill.boe_collected_amount, 200)
                self.assertEqual(invoice.amount_residual, 0)
                self.assertEqual(invoice.payment_state, "in_payment")
                with self.assertRaises(UserError), self.env.cr.savepoint():
                    collection.action_confirm()
                collection.action_cancel()
                self.assertEqual(collection.state, "canceled")
                self.assertEqual(bill.boe_active_amount, bill.amount)
                self.assertEqual(bill.boe_collected_amount, 0)
                final_collection = self._collect(bill, bill.amount, bank=True)
                final_collection.action_confirm()
                self.assertEqual(bill.state, "paid")
                self.assertEqual(invoice.payment_state, "paid")
                self.assertEqual(bill.boe_collected_amount, bill.amount)

    def test_bank_collection_using_bank_account_confirms_immediately(self):
        self.bank_method.payment_account_id = self.bank_journal.default_account_id
        invoice = self._invoice()
        bill = self._bill(invoice)
        collection = self._collect(bill, bill.amount, bank=True)
        self.assertEqual(collection.state, "confirmed")
        self.assertTrue(collection.payment_id.is_matched)
        self.assertEqual(bill.boe_active_amount, 0)
        self.assertEqual(bill.boe_pending_amount, 0)
        self.assertEqual(bill.state, "paid")
        self.assertEqual(invoice.payment_state, "paid")

    def test_manual_bank_recovery_confirmation(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        incident = self._unpaid(bill, 600)
        recovery = self._collect(bill, 150, bank=True, incident=incident)
        self.assertEqual(recovery.state, "pending")
        self.assertEqual(incident.recovery_residual, 600)
        recovery.action_confirm()
        self.assertEqual(recovery.state, "confirmed")
        self.assertFalse(recovery.payment_id.is_matched)
        self.assertEqual(recovery.recovered_amount, 150)
        self.assertEqual(incident.recovery_residual, 450)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 150)
        self.assertEqual(bill.boe_collected_amount, 0)

    def test_bank_collection_without_method_account(self):
        self.bank_method.payment_account_id = False
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        collection = self._collect(bill, 200, bank=True)
        payment = collection.payment_id
        self.assertFalse(self.bank_method.payment_account_id)
        self.assertTrue(payment.outstanding_account_id)
        self.assertNotEqual(payment.outstanding_account_id, bill.outstanding_account_id)
        self.assertEqual(payment.move_id.state, "posted")
        liquidity, counterpart, writeoff = payment._seek_for_lines()
        self.assertEqual(sum(liquidity.mapped("balance")), 200)
        self.assertEqual(counterpart.balance, -200)
        self.assertEqual(counterpart.account_id, bill.outstanding_account_id)
        self.assertFalse(writeoff)
        self.assertEqual(collection.state, "pending")
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(bill.boe_pending_amount, 200)
        self.assertEqual(bill.boe_collected_amount, 0)
        self._bank_match(collection)
        collection.action_confirm()
        self.assertEqual(collection.state, "confirmed")
        self.assertEqual(bill.boe_active_amount, 400)
        self.assertEqual(bill.boe_pending_amount, 0)
        self.assertEqual(bill.boe_collected_amount, 200)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 600)

    def test_collection_account_must_differ_from_bill_account(self):
        bill = self._bill(self._invoice(), 600)
        self.bank_method.payment_account_id = bill.outstanding_account_id
        with self.assertRaisesRegex(UserError, "distinct"), self.env.cr.savepoint():
            self._collect(bill, 200, bank=True)
        self.assertFalse(bill.boe_settlement_ids)
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(bill.boe_pending_amount, 0)

    def test_collection_payment_matches_principal(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        collection = self._collect(bill, 200)
        self.assertEqual(collection.payment_id.amount, 200)
        self.assertEqual(len(collection.payment_id.move_id.line_ids), 2)
        self.assertEqual(collection.collected_amount, 200)
        self.assertEqual(bill.boe_active_amount, 400)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 600)

    def test_unpaid_without_document_requires_reason(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._operation(
                bill,
                "unpaid",
                600,
                journal_id=self.chart.ref("general").id,
            )
        self.assertFalse(bill.boe_incident_ids)
        self.assertEqual(bill.boe_active_amount, 600)
        self._operation(
            bill,
            "unpaid",
            600,
            journal_id=self.chart.ref("general").id,
            reason="Debtor did not pay",
        )
        self.assertEqual(len(bill.boe_incident_ids), 1)
        self.assertEqual(bill.boe_incident_ids.amount, 600)
        self.assertEqual(bill.boe_incident_ids.recovery_residual, 600)
        self.assertEqual(bill.boe_incident_ids.return_move_id.state, "posted")
        self.assertEqual(len(bill.boe_incident_ids.return_move_id.line_ids), 2)
        self.assertEqual(
            sum(bill.boe_incident_ids.return_move_id.line_ids.mapped("debit")), 600
        )
        self.assertEqual(bill.boe_active_amount, 0)
        self.assertEqual(bill.state, "rejected")
        self.assertEqual(invoice.amount_residual, invoice.amount_total)

    def test_partial_collection_then_unpaid_and_recovery(self):
        invoice = self._invoice()
        bill = self._bill(invoice, 600)
        self._collect(bill, 200)
        incident = self._unpaid(bill, 400)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 200)
        self.assertEqual(bill.boe_active_amount, 0)
        self.assertEqual(bill.boe_collected_amount, 200)
        self.assertEqual(incident.recovery_residual, 400)
        self.assertEqual(bill.state, "rejected")
        self._collect(bill, 150, incident=incident)
        self.assertEqual(incident.recovery_residual, 250)
        self.assertEqual(bill.boe_recovery_amount, 150)
        self.assertEqual(invoice.amount_residual, invoice.amount_total - 350)

    def test_unpaid_multi_invoice_does_not_duplicate_debt(self):
        invoices = self._invoice(700) | self._invoice(500)
        bill = self._bill(invoices)
        self._unpaid(bill, bill.amount)
        self.assertEqual(
            sum(invoices.mapped("amount_residual")),
            sum(invoices.mapped("amount_total")),
        )
        self.assertEqual(sum(bill.boe_incident_ids.mapped("amount")), bill.amount)
        self.assertEqual(bill.boe_active_amount, 0)
        self.assertEqual(bill.boe_recovery_residual, bill.amount)

    def test_reverse_confirmed_collection_restores_effect(self):
        bill = self._bill(self._invoice(), 600)
        collection = self._collect(bill, 200)
        collection.action_cancel()
        self.assertEqual(collection.state, "canceled")
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(bill.boe_collected_amount, 0)

    def test_remove_bank_matching_reopens_collection(self):
        bill = self._bill(self._invoice(), 600)
        collection = self._collect(bill, 200, bank=True)
        self._bank_match(collection)
        collection.action_confirm()
        self.assertEqual(bill.boe_active_amount, 400)
        collection.payment_id._seek_for_lines()[0].remove_move_reconcile()
        self.assertEqual(collection.state, "pending")
        self.assertEqual(bill.boe_active_amount, 600)
        self.assertEqual(bill.boe_pending_amount, 200)

    def test_replacement_is_not_a_cash_recovery(self):
        invoice = self._invoice()
        old = self._bill(invoice, 600)
        incident = self._unpaid(old, 600)
        replacement = self._bill(invoice, 600, boe_replaced_payment_id=old.id)
        self.assertEqual(incident.recovery_residual, 0)
        self.assertEqual(incident.transferred_amount, 600)
        self.assertEqual(old.boe_recovery_amount, 0)
        self.assertEqual(replacement.boe_active_amount, 600)
        self._operation(replacement, "cancel", reason="Replacement entered in error")
        self.assertEqual(incident.recovery_residual, 600)

    def test_no_collection_over_available_or_workflow_bypass(self):
        bill = self._bill(self._invoice(), 600)
        self._collect(bill, 400, bank=True)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._collect(bill, 300)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            bill.action_validate()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            bill.write({"boe_active_amount": 0})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            bill.write({"amount": 200})

    def test_operation_cannot_be_replayed(self):
        bill = self._bill(self._invoice(), 600)
        wizard = self._operation(
            bill,
            "collect",
            200,
            journal_id=self.cash_journal.id,
            payment_method_line_id=self.cash_method.id,
        )
        with self.assertRaises(UserError), self.env.cr.savepoint():
            wizard.action_apply()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            wizard.done = False
        self.assertEqual(bill.boe_collected_amount, 200)

    def test_followup_is_idempotent_and_keeps_promises_nonfinancial(self):
        bill = self._bill(self._invoice(), 600)
        bill.write(
            {
                "boe_promise_date": self.today - timedelta(days=1),
                "boe_promise_amount": 600,
            }
        )
        self.env["account.payment"]._cron_boe_followup()
        before = bill.activity_ids
        self.env["account.payment"]._cron_boe_followup()
        self.assertEqual(bill.activity_ids, before)
        self.assertTrue(before)
        self.assertEqual(bill.boe_collected_amount, 0)

    def test_chart_setup_is_idempotent(self):
        journal = self.bill_method.journal_id
        self.assertTrue(journal, "The chart must link the bill method to its journal")
        self.assertEqual(journal, self.chart.ref("tn_boe"))
        self.assertEqual(journal.inbound_payment_method_line_ids, self.bill_method)
        self.assertFalse(journal.outbound_payment_method_line_ids)
        journal.name = "Customized bill journal"
        self.env.company.action_setup_tn_boe()
        self.env.company.action_setup_tn_boe()
        self.assertEqual(self.chart.ref("tn_boe"), journal)
        self.assertEqual(journal.name, "Customized bill journal")
        self.assertEqual(journal.type, "bank")
        self.assertFalse(journal.show_on_dashboard)
        self.assertEqual(journal.inbound_payment_method_line_ids, self.bill_method)

    def test_chart_setup_repairs_detached_bill_method(self):
        journal = self.chart.ref("tn_boe")
        account = self.bill_method.payment_account_id
        self.bill_method.journal_id = False
        self.env.company.action_setup_tn_boe()
        self.env.company.action_setup_tn_boe()
        self.assertEqual(self.chart.ref("tn_boe_inbound"), self.bill_method)
        self.assertEqual(self.bill_method.journal_id, journal)
        self.assertEqual(self.bill_method.payment_account_id, account)
        self.assertEqual(journal.inbound_payment_method_line_ids, self.bill_method)

    def test_readonly_user_cannot_collect(self):
        bill = self._bill(self._invoice(), 600)
        reader = new_test_user(
            self.env,
            login="bill_reader",
            groups="account.group_account_readonly",
            company_id=self.env.company.id,
        )
        self.assertTrue(bill.with_user(reader).boe_active_amount)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            bill.with_user(reader).action_boe_operation()

    def test_accountant_can_operate_without_history_edit_rights(self):
        bill = self._bill(self._invoice(), 600)
        accountant = new_test_user(
            self.env,
            login="bill_operator",
            groups="account.group_account_invoice",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        self.env["l10n_tn.boe.operation"].with_user(accountant).create(
            {
                "bill_id": bill.id,
                "operation": "collect",
                "amount": 200,
                "date": self.today,
                "reference": "Accountant collection",
                "journal_id": self.cash_journal.id,
                "payment_method_line_id": self.cash_method.id,
            }
        ).action_apply()
        collection = bill.boe_settlement_ids
        self.assertEqual(collection.state, "confirmed")
        self.assertEqual(bill.boe_active_amount, 400)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            collection.with_user(accountant).write({"amount": 1})
        incident = self._unpaid(bill, 400)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            incident.with_user(accountant).write({"amount": 1})
        self.env["l10n_tn.boe.operation"].with_user(accountant).create(
            {
                "bill_id": bill.id,
                "operation": "recover",
                "incident_id": incident.id,
                "amount": 150,
                "date": self.today,
                "reference": "Accountant recovery",
                "journal_id": self.cash_journal.id,
                "payment_method_line_id": self.cash_method.id,
            }
        ).action_apply()
        self.assertEqual(incident.recovery_residual, 250)

    def test_initial_state_cannot_skip_signed_receipt(self):
        invoice = self._invoice()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._bill(invoice, 600, post=False, state="paid")

    def test_foreign_currency_is_rejected(self):
        invoice = self._invoice()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._bill(
                invoice, 600, post=False, currency_id=self.env.ref("base.EUR").id
            )

    def test_spreadsheet_has_live_sources_and_no_public_snapshot(self):
        module = "l10n_tn_account_payment_bill_of_exchange"
        with file_open(f"{module}/data/bill_dashboard.json") as source:
            snapshot = json.load(source)
        self.assertEqual(len(snapshot["sheets"]), 5)
        self.assertEqual(
            {pivot["model"] for pivot in snapshot["pivots"].values()},
            {"account.payment", "l10n_tn.boe.incident", "l10n_tn.boe.settlement"},
        )
        dashboard = self.env.ref(f"{module}.dashboard_boe")
        data = json.loads(dashboard._get_serialized_readonly_dashboard())
        self.assertNotEqual(
            data["snapshot"]["sheets"][0]["cells"]["B2"], "Chargement en cours"
        )
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["spreadsheet.dashboard.share"].create(
                {"dashboard_id": dashboard.id}
            )
