# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import new_test_user, tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingPaymentReception(WithholdingTaxTestCommon):
    def _register_withholding(self, move):
        journal = (
            self.inbound_withholding_journal
            if move.move_type == "out_invoice"
            else self.withholding_journal
        )
        wizard = self._create_payment_wizard(move)
        with Form(wizard) as form:
            form.journal_id = journal
        return wizard._create_payments()

    def _check_certificate_flow(self, move_type):
        invoice = self._create_move(self.product_a, 2000, move_type=move_type)
        payment = self._register_withholding(invoice)

        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)
        self.assertTrue(payment.is_reconciled)
        self.assertFalse(payment.withholding_reception_confirmed)
        self.assertAlmostEqual(
            invoice.amount_residual, invoice.amount_total - payment.amount
        )
        self.assertNotIn(
            payment.journal_id,
            self._create_payment_wizard(invoice).available_journal_ids,
        )

        bank_journal = self.company_data["default_journal_bank"]
        methods = (
            bank_journal.inbound_payment_method_line_ids
            if payment.payment_type == "inbound"
            else bank_journal.outbound_payment_method_line_ids
        )
        methods.payment_account_id = bank_journal.default_account_id
        balance_wizard = self._create_payment_wizard(invoice)
        with Form(balance_wizard) as form:
            form.journal_id = bank_journal
        balance_payment = balance_wizard._create_payments()

        self.assertTrue(balance_payment.is_matched)
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(invoice.payment_state, "in_payment")
        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)
        journal_entry = payment.move_id
        journal_items = journal_entry.line_ids

        # standard validation must follow certificate confirmation too
        payment.action_validate()

        self.assertEqual(payment.state, "paid")
        self.assertTrue(payment.is_matched)
        self.assertTrue(payment.withholding_reception_confirmed)
        self.assertTrue(payment.withholding_reception_date)
        self.assertEqual(payment.withholding_reception_user_id, self.env.user)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(payment.move_id, journal_entry)
        self.assertEqual(payment.move_id.line_ids, journal_items)

    def test_incoming_certificate_reception(self):
        self._check_certificate_flow("out_invoice")

    def test_outgoing_certificate_delivery(self):
        self._check_certificate_flow("in_invoice")

    def test_reset_clears_confirmation_and_requires_revalidation(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        payment.action_validate_withholding()

        payment.action_draft()

        self.assertEqual(payment.state, "draft")
        self.assertFalse(payment.withholding_reception_confirmed)
        self.assertFalse(payment.withholding_reception_user_id)
        self.assertFalse(payment.withholding_reception_date)
        self.assertFalse(payment.is_matched)
        payment.action_post()
        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)

    def test_batch_validation_and_duplicate_validation(self):
        first_invoice = self._create_move(self.product_a, 2000)
        second_invoice = self._create_move(self.product_a, 3000)
        payments = self._register_withholding(first_invoice)
        payments |= self._register_withholding(second_invoice)

        payments.action_validate_withholding()

        self.assertEqual(payments.mapped("state"), ["paid", "paid"])
        self.assertTrue(all(payments.mapped("is_matched")))
        with self.assertRaises(UserError):
            payments.action_validate_withholding()

    def test_draft_certificate_cannot_be_validated(self):
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.withholding_journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": 30,
            }
        )
        with self.assertRaises(UserError):
            payment.action_validate_withholding()

    def test_standalone_foreign_withholding_payment_is_rejected(self):
        self.partner_a.country_id = self.env.ref("base.fr")
        with self.assertRaises(ValidationError):
            self.env["account.payment"].create(
                {
                    "journal_id": self.withholding_journal.id,
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": self.partner_a.id,
                    "amount": 30,
                }
            )

    def test_country_change_before_posting_withholding_is_rejected(self):
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.withholding_journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": 30,
            }
        )
        self.partner_a.country_id = self.env.ref("base.fr")
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_direct_withholding_refund_is_rejected(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        for partner_type, direction in (
            ("customer", "outbound"),
            ("supplier", "inbound"),
        ):
            with self.subTest(partner_type=partner_type, direction=direction):
                with (
                    self.assertRaisesRegex(ValidationError, "refunds"),
                    self.cr.savepoint(),
                ):
                    self.env["account.payment"].create(
                        {
                            "journal_id": journal.id,
                            "partner_id": self.partner_a.id,
                            "partner_type": partner_type,
                            "payment_type": direction,
                            "amount": 30,
                        }
                    )

    def test_refund_document_cannot_be_hidden_by_payment_direction(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        for move_type, partner_type, direction in (
            ("out_refund", "customer", "inbound"),
            ("in_refund", "supplier", "outbound"),
        ):
            with self.subTest(move_type=move_type):
                refund = self._create_move(self.product_a, 2000, move_type=move_type)
                with (
                    self.assertRaisesRegex(ValidationError, "refunds"),
                    self.cr.savepoint(),
                ):
                    self.env["account.payment"].create(
                        {
                            "journal_id": journal.id,
                            "partner_id": self.partner_a.id,
                            "partner_type": partner_type,
                            "payment_type": direction,
                            "invoice_ids": [Command.set(refund.ids)],
                            "amount": 30,
                        }
                    )

    def test_payment_direction_cannot_be_changed_to_a_withholding_refund(self):
        journal = self.withholding_journal
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        payment = self.env["account.payment"].create(
            {
                "journal_id": journal.id,
                "partner_id": self.partner_a.id,
                "partner_type": "customer",
                "payment_type": "inbound",
                "amount": 30,
            }
        )
        with (
            self.assertRaisesRegex(ValidationError, "refunds"),
            self.cr.savepoint(),
        ):
            payment.payment_type = "outbound"

    def test_inactive_states_cannot_keep_certificate_confirmation_via_orm(self):
        for state in ("draft", "canceled", "rejected"):
            with self.subTest(state=state):
                with (
                    self.assertRaises(ValidationError),
                    self.cr.savepoint(),
                ):
                    self.env["account.payment"].create(
                        {
                            "journal_id": self.withholding_journal.id,
                            "payment_type": "outbound",
                            "partner_type": "supplier",
                            "partner_id": self.partner_a.id,
                            "amount": 30,
                            "state": state,
                            "withholding_reception_confirmed": True,
                        }
                    )

    def test_consistent_confirmation_can_be_written_via_orm(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        date = fields.Datetime.now()
        payment.write(
            {
                "withholding_reception_confirmed": True,
                "withholding_reception_date": date,
                "withholding_reception_user_id": self.env.user.id,
            }
        )
        self.assertTrue(payment.withholding_reception_confirmed)
        self.assertEqual(payment.withholding_reception_date, date)
        self.assertEqual(payment.withholding_reception_user_id, self.env.user)
        self.assertEqual(payment.state, "paid")
        payment.write(
            {
                "withholding_reception_confirmed": False,
                "withholding_reception_date": False,
                "withholding_reception_user_id": False,
            }
        )
        self.assertFalse(payment.withholding_reception_confirmed)
        self.assertEqual(payment.state, "in_process")

    def test_incomplete_confirmation_is_rejected_via_orm(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        values = {
            "withholding_reception_confirmed": True,
            "withholding_reception_date": fields.Datetime.now(),
            "withholding_reception_user_id": self.env.user.id,
        }
        for missing_field in values:
            with self.subTest(missing_field=missing_field):
                incomplete = dict(values, **{missing_field: False})
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    payment.write(incomplete)
        self.assertFalse(payment.withholding_reception_confirmed)

    def test_confirmation_without_entry_is_rejected_on_create(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["account.payment"].create(
                {
                    "journal_id": self.withholding_journal.id,
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": self.partner_a.id,
                    "amount": 30,
                    "state": "in_process",
                    "withholding_reception_confirmed": True,
                    "withholding_reception_date": fields.Datetime.now(),
                    "withholding_reception_user_id": self.env.user.id,
                }
            )

    def test_confirmation_requires_a_posted_entry(self):
        payment = self.env["account.payment"].create(
            {
                "journal_id": self.withholding_journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": 30,
            }
        )
        self.assertEqual(payment.state, "draft")
        self.assertFalse(payment.move_id)
        with self.assertRaisesRegex(UserError, "Only pending withholding"):
            payment.action_validate_withholding()
        payment._generate_journal_entry()
        self.assertEqual(payment.state, "in_process")
        self.assertEqual(payment.move_id.state, "draft")
        with self.assertRaisesRegex(UserError, "posted journal entry"):
            payment.action_validate_withholding()
        self.assertFalse(payment.withholding_reception_confirmed)

    def test_batch_confirmation_checks_all_entries_before_writing(self):
        invoice = self._create_move(self.product_a, 2000)
        valid = self._register_withholding(invoice)
        invalid = self.env["account.payment"].create(
            {
                "journal_id": self.withholding_journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "amount": 30,
            }
        )
        invalid._generate_journal_entry()
        self.assertEqual(invalid.state, "in_process")
        self.assertEqual(invalid.move_id.state, "draft")
        with self.assertRaisesRegex(UserError, "posted journal entry"):
            (valid | invalid).action_validate_withholding()
        self.assertFalse(valid.withholding_reception_confirmed)
        self.assertFalse(invalid.withholding_reception_confirmed)

    def test_confirmation_requires_accounting_rights_and_company_access(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        internal = new_test_user(
            self.env, login="certificate_internal", groups="base.group_user"
        )
        with self.assertRaises(AccessError):
            payment.with_user(internal).action_validate_withholding()
        accountant = new_test_user(
            self.env,
            login="certificate_accountant",
            groups="account.group_account_invoice",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        other_company = self.setup_other_company()["company"]
        with self.assertRaises(AccessError):
            payment.with_user(accountant).with_context(
                allowed_company_ids=other_company.ids
            ).action_validate_withholding()
        payment.with_user(accountant).action_validate_withholding()
        self.assertEqual(payment.withholding_reception_user_id, accountant)
        self.assertTrue(payment.withholding_reception_date)

    def test_lifecycle_actions_preserve_states_and_clear_confirmation(self):
        for action, expected in (
            ("action_draft", "draft"),
            ("action_cancel", "canceled"),
            ("action_reject", "rejected"),
        ):
            for confirmed in (False, True):
                with self.subTest(action=action, confirmed=confirmed):
                    invoice = self._create_move(self.product_a, 2000)
                    payment = self._register_withholding(invoice)
                    if confirmed:
                        payment.action_validate_withholding()
                    getattr(payment, action)()
                    self.assertEqual(payment.state, expected)
                    self.assertFalse(payment.withholding_reception_confirmed)
                    self.assertFalse(payment.withholding_reception_date)
                    self.assertFalse(payment.withholding_reception_user_id)
                    self.env.add_to_compute(payment._fields["state"], payment)
                    payment.flush_recordset(["state"])
                    self.assertEqual(payment.state, expected)
                    self.assertFalse(payment.is_matched)

    def test_confirmed_payment_follows_its_entry_posting_state(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        payment.action_validate_withholding()
        self.assertEqual(payment.state, "paid")
        self.assertTrue(payment.is_matched)

        payment.move_id.button_draft()

        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)
        self.assertTrue(payment.withholding_reception_confirmed)

        payment.move_id.action_post()

        self.assertEqual(payment.state, "paid")
        self.assertTrue(payment.is_matched)

    def test_mixed_state_recomputation_preserves_standard_payments(self):
        invoice = self._create_move(self.product_a, 2000)
        withholding = self._register_withholding(invoice)
        journal = self.company_data["default_journal_bank"]
        journal.inbound_payment_method_line_ids.payment_account_id = (
            journal.default_account_id
        )
        ordinary = self.env["account.payment"].create(
            {
                "journal_id": journal.id,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 50,
            }
        )
        ordinary.action_post()
        payments = ordinary | withholding
        self.env.add_to_compute(payments._fields["state"], payments)
        payments.flush_recordset(["state"])
        self.assertEqual(ordinary.state, "paid")
        self.assertTrue(ordinary.is_matched)
        self.assertEqual(withholding.state, "in_process")
        self.assertFalse(withholding.is_matched)
        withholding.action_validate_withholding()
        self.env.add_to_compute(payments._fields["state"], payments)
        payments.flush_recordset(["state"])
        self.assertEqual(ordinary.state, "paid")
        self.assertTrue(ordinary.is_matched)
        self.assertEqual(withholding.state, "paid")
        self.assertTrue(withholding.is_matched)

    def test_direct_state_change_cannot_keep_confirmed_certificate(self):
        invoice = self._create_move(self.product_a, 2000)
        payment = self._register_withholding(invoice)
        payment.action_validate_withholding()
        with (
            self.assertRaisesRegex(ValidationError, "cannot retain certificate"),
            self.cr.savepoint(),
        ):
            payment.state = "draft"
        self.assertTrue(payment.withholding_reception_confirmed)

    def test_standard_outstanding_payment_waits_for_reconciliation(self):
        journal = self.company_data["default_journal_bank"]
        outstanding = self.tax_receivable.copy(
            {"code": "991508", "name": "Standard outstanding receipts"}
        )
        journal.inbound_payment_method_line_ids.payment_account_id = outstanding
        payment = self.env["account.payment"].create(
            {
                "journal_id": journal.id,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 50,
            }
        )
        payment.action_post()
        self.assertFalse(payment.is_withholding_tax_payment)
        self.assertEqual(payment.state, "in_process")
        self.assertFalse(payment.is_matched)
        settlement = self.env["account.move"].create(
            {
                "journal_id": self.company_data["default_journal_misc"].id,
                "date": payment.date,
                "line_ids": [
                    Command.create(
                        {"account_id": journal.default_account_id.id, "debit": 50}
                    ),
                    Command.create(
                        {
                            "account_id": outstanding.id,
                            "credit": 50,
                            "partner_id": self.partner_a.id,
                        }
                    ),
                ],
            }
        )
        settlement.action_post()
        liquidity, _counterpart, _writeoff = payment._seek_for_lines()
        settlement_line = settlement.line_ids.filtered(
            lambda line: line.account_id == outstanding
        )
        (liquidity + settlement_line).reconcile()
        self.assertEqual(payment.state, "paid")
        self.assertTrue(payment.is_matched)
        self.assertFalse(payment.withholding_reception_confirmed)
