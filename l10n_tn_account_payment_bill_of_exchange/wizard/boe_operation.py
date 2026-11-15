# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from ..models.account_payment import BOE_OPERATION


class BoeOperation(models.TransientModel):
    _name = "l10n_tn.boe.operation"
    _description = "Bill Operation"
    _check_company_auto = True

    bill_id = fields.Many2one("account.payment", required=True, check_company=True)
    company_id = fields.Many2one(related="bill_id.company_id")
    currency_id = fields.Many2one(related="bill_id.currency_id")
    operation = fields.Selection(
        [
            ("collect", "Collect"),
            ("recover", "Recover Unpaid Principal"),
            ("unpaid", "Declare Unpaid"),
            ("cancel", "Cancel"),
        ],
        required=True,
        default="collect",
    )
    incident_id = fields.Many2one("l10n_tn.boe.incident", check_company=True)
    amount = fields.Monetary()
    date = fields.Date(required=True, default=fields.Date.context_today)
    reference = fields.Char(required=True)
    reason = fields.Char()
    journal_id = fields.Many2one("account.journal", check_company=True)
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        check_company=True,
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'inbound')]",
    )
    source_line_id = fields.Many2one(
        "account.move.line",
        check_company=True,
        domain="[('company_id', '=', company_id), ('parent_state', '=', 'posted'),"
        " ('credit', '>', 0), ('reconciled', '=', False)]",
        help="Optional existing payment or bank transaction; its available credit "
        "must equal the principal.",
    )
    document = fields.Binary()
    document_name = fields.Char()
    done = fields.Boolean(readonly=True, groups="base.group_no_one")

    @api.model
    def default_get(self, field_names):
        result = super().default_get(field_names)
        bill = self.env["account.payment"].browse(result.get("bill_id"))
        if bill and result.get("operation") == "unpaid":
            chart = self.env["account.chart.template"].with_company(bill.company_id)
            result["journal_id"] = chart.ref("general").id
        return result

    @api.onchange("journal_id")
    def _onchange_boe_journal(self):
        self.payment_method_line_id = (
            self.journal_id.inbound_payment_method_line_ids.filtered(
                lambda method: method.code != "tn_bill_of_exchange"
            )[:1]
        )

    @api.onchange("source_line_id")
    def _onchange_boe_source(self):
        if self.source_line_id:
            self.date = self.source_line_id.date
            self.reference = (
                self.source_line_id.move_id.ref or self.source_line_id.move_id.name
            )

    def action_apply(self):
        self.ensure_one()
        bill = self.bill_id
        bill._boe_check_accountant(manager=self.operation == "cancel")
        bill._boe_lock()
        self.lock_for_update()
        self.invalidate_recordset()
        if self.sudo().done:
            raise UserError(self.env._("This operation has already been applied."))
        if not bill.tn_boe or bill.company_id not in self.env.companies:
            raise UserError(self.env._("Select an authorized bill of exchange."))
        if self.date > fields.Date.context_today(self):
            raise UserError(
                self.env._("An actual operation cannot be dated in the future.")
            )
        if self.operation != "cancel" and bill.move_id.state != "posted":
            raise UserError(self.env._("Confirm receipt of the bill first."))
        if self.operation in ("collect", "recover"):
            self._collect()
        elif self.operation == "unpaid":
            self._unpaid()
        elif self.operation == "cancel":
            self._cancel()
        else:
            raise UserError(self.env._("Select a supported bill operation."))
        self.sudo().done = True
        bill.message_post(
            body=self.env._(
                "Bill operation %(operation)s: %(reference)s",
                operation=dict(self._fields["operation"].selection)[self.operation],
                reference=self.reference,
            )
        )
        return {"type": "ir.actions.act_window_close"}

    def _collect(self):
        bill = self.bill_id
        incident = self.incident_id
        if self.operation == "recover":
            if not incident or incident.bill_id != bill or incident.state != "posted":
                raise UserError(
                    self.env._("Select a posted unpaid incident for this bill.")
                )
            available = incident.recovery_residual - incident.pending_amount
        else:
            if incident:
                raise UserError(
                    self.env._("Use the recovery operation for an unpaid incident.")
                )
            available = bill.boe_available_amount
        if (
            self.currency_id.compare_amounts(self.amount, 0) <= 0
            or self.currency_id.compare_amounts(self.amount, available) > 0
        ):
            raise UserError(
                self.env._(
                    "The collection must be positive and within the "
                    "available principal."
                )
            )
        account = (
            incident.invoice_line_id.account_id
            if incident
            else bill.outstanding_account_id
        )
        payment = self.env["account.payment"]
        source = self.source_line_id
        if source:
            payment = self._check_existing_source(account)
        else:
            payment = self._create_collection_payment(account)
            source = payment._seek_for_lines()[1]
            if len(source) != 1:
                raise UserError(
                    self.env._(
                        "The actual payment must have one receivable counterpart."
                    )
                )
        settlement = (
            self.env["l10n_tn.boe.settlement"]
            .sudo()
            .create(
                {
                    "bill_id": bill.id,
                    "incident_id": incident.id,
                    "amount": self.amount,
                    "date": self.date,
                    "reference": self.reference,
                    "payment_id": payment.id,
                    "source_line_id": source.id,
                }
            )
        )
        if payment:
            payment.with_context(
                tn_boe_operation=BOE_OPERATION
            ).boe_source_settlement_id = settlement
        source.with_context(
            tn_boe_operation=BOE_OPERATION
        ).tn_boe_collection_id = settlement
        if (payment and (payment.is_matched or payment.state == "paid")) or (
            not payment and source.move_id.statement_line_id
        ):
            settlement.sudo(False).action_confirm()
        self._attach_document(settlement.sudo(False))

    def _check_existing_source(self, account):
        source = self.source_line_id
        source.check_access("write")
        source.lock_for_update()
        source.invalidate_recordset()
        payment = source.move_id.origin_payment_id
        if not payment and not source.move_id.statement_line_id:
            raise UserError(
                self.env._("Select an actual payment or bank transaction credit.")
            )
        if payment.boe_source_settlement_id:
            raise UserError(self.env._("This payment already belongs to a collection."))
        if (
            source.move_id.state != "posted"
            or source.company_id != self.company_id
            or source.account_id != account
            or source.partner_id.commercial_partner_id
            != self.bill_id.partner_id.commercial_partner_id
            or source.currency_id != self.currency_id
            or self.currency_id.compare_amounts(-source.amount_residual, self.amount)
            != 0
            or source.date != self.date
        ):
            raise UserError(
                self.env._(
                    "The source credit must match the bill account, customer "
                    "and principal."
                )
            )
        return payment

    def _create_collection_payment(self, account):
        method = self.payment_method_line_id
        if (
            not method
            or method.journal_id != self.journal_id
            or method.payment_type != "inbound"
            or method.code == "tn_bill_of_exchange"
            or self.journal_id.tn_boe_journal
            or self.journal_id.company_id != self.company_id
            or self.journal_id.type not in ("bank", "cash")
            or (
                self.journal_id.currency_id
                and self.journal_id.currency_id != self.currency_id
            )
        ):
            raise UserError(
                self.env._(
                    "Select an incoming payment method from a real bank/cash journal "
                    "in the bill company and currency."
                )
            )
        payment = (
            self.env["account.payment"]
            .with_context(
                tn_boe_operation=BOE_OPERATION,
                # bill settlement needs an entry, let Odoo resolve a missing account
                force_payment_move=not method.payment_account_id,
            )
            .create(
                {
                    "partner_id": self.bill_id.partner_id.id,
                    "company_id": self.company_id.id,
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "amount": self.amount,
                    "currency_id": self.currency_id.id,
                    "date": self.date,
                    "journal_id": self.journal_id.id,
                    "payment_method_line_id": method.id,
                    "destination_account_id": account.id,
                    "memo": self.reference,
                    "payment_reference": self.reference,
                }
            )
        )
        if (
            not payment.outstanding_account_id
            or payment.outstanding_account_id == account
        ):
            raise UserError(
                self.env._(
                    "The payment collection account must be distinct from the bill "
                    "counterpart account."
                )
            )
        payment.action_post()
        if payment.move_id.state != "posted":
            raise UserError(
                self.env._(
                    "The actual payment needs a posted entry to settle the bill."
                )
            )
        return payment

    def _unpaid(self):
        bill = self.bill_id
        if (
            not self.reason
            or self.currency_id.compare_amounts(self.amount, 0) <= 0
            or self.currency_id.compare_amounts(self.amount, bill.boe_available_amount)
            > 0
            or bill.boe_pending_amount
        ):
            raise UserError(
                self.env._(
                    "Provide an incident reason and an available positive principal; "
                    "resolve pending collections first."
                )
            )
        journal = self.journal_id
        if (
            not journal
            or journal.type != "general"
            or journal.company_id != self.company_id
        ):
            raise UserError(
                self.env._("Choose a miscellaneous journal in the bill company.")
            )
        _liquidity, counterpart, _writeoff = bill._seek_for_lines()
        allocations = counterpart.matched_debit_ids.filtered(
            lambda p: p.debit_move_id.move_id in bill.boe_invoice_ids
        ).sorted("id")
        remaining = self.amount
        for allocation in allocations:
            if self.currency_id.is_zero(remaining):
                break
            amount = min(remaining, allocation.amount)
            incident = self._return_allocation(allocation, amount)
            self._attach_document(incident)
            remaining -= amount
        if not self.currency_id.is_zero(remaining):
            raise UserError(
                self.env._(
                    "The original invoice allocations no longer cover this return."
                )
            )
        if self.currency_id.is_zero(bill.boe_active_amount):
            bill.with_context(tn_boe_operation=BOE_OPERATION).write(
                {
                    "state": "rejected",
                    "boe_custody": "returned",
                }
            )

    def _return_allocation(self, allocation, amount):
        bill = self.bill_id
        invoice_line = allocation.debit_move_id
        credit = allocation.credit_move_id
        move = (
            self.env["account.move"]
            .with_context(tn_boe_operation=BOE_OPERATION)
            .create(
                {
                    "journal_id": self.journal_id.id,
                    "date": self.date,
                    "ref": self.reference,
                    "partner_id": bill.partner_id.id,
                    "line_ids": [
                        Command.create(
                            {
                                "account_id": invoice_line.account_id.id,
                                "partner_id": bill.partner_id.id,
                                "name": self.reason,
                                "debit": amount,
                                "date_maturity": bill.boe_maturity_date,
                            }
                        ),
                        Command.create(
                            {
                                "account_id": bill.outstanding_account_id.id,
                                "partner_id": bill.partner_id.id,
                                "name": self.reason,
                                "credit": amount,
                                "date_maturity": bill.boe_maturity_date,
                            }
                        ),
                    ],
                }
            )
        )
        move.action_post()
        returned = move.line_ids.filtered_domain(
            [("account_id", "=", invoice_line.account_id.id)]
        )
        effect_credit = move.line_ids.filtered_domain(
            [("account_id", "=", bill.outstanding_account_id.id)]
        )
        allocation.with_context(tn_boe_operation=BOE_OPERATION).unlink()
        (credit + returned).reconcile()
        # restore the retained fraction without disturbing other invoice payments
        retained = (credit + invoice_line).filtered(lambda line: not line.reconciled)
        if len(retained) == 2:
            retained.reconcile()
        (bill._seek_for_lines()[0] + effect_credit).with_context(
            tn_boe_operation=BOE_OPERATION
        ).reconcile()
        incident = (
            self.env["l10n_tn.boe.incident"]
            .sudo()
            .create(
                {
                    "bill_id": bill.id,
                    "invoice_id": invoice_line.move_id.id,
                    "invoice_line_id": invoice_line.id,
                    "return_move_id": move.id,
                    "return_line_id": returned.id,
                    "date": self.date,
                    "reason": self.reason,
                    "amount": amount,
                }
            )
        )
        move.tn_boe_incident_id = incident
        return incident.sudo(False)

    def _cancel(self):
        bill = self.bill_id
        if not self.reason or bill.state in ("canceled", "rejected"):
            raise UserError(
                self.env._("Provide a cancellation reason for an active or draft bill.")
            )
        if bill.boe_settlement_ids or bill.boe_incident_ids:
            raise UserError(
                self.env._(
                    "Reverse collections and use the unpaid procedure for a bill with "
                    "financial history."
                )
            )
        if bill.move_id.state == "posted":
            bill.move_id.with_context(tn_boe_operation=BOE_OPERATION)._reverse_moves(
                [{"date": self.date, "ref": self.reason}],
                cancel=True,
            )
        bill.with_context(tn_boe_operation=BOE_OPERATION).write(
            {
                "state": "canceled",
                "boe_custody": "returned",
            }
        )

    def _attach_document(self, record):
        if self.document:
            # the caller has already checked accounting rights and bill access,
            # elevate only the attachment on the immutable history record
            self.env["ir.attachment"].sudo().create(
                {
                    "name": self.document_name or self.reference,
                    "datas": self.document,
                    "res_model": record._name,
                    "res_id": record.id,
                }
            )
