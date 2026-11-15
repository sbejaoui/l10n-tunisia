# Copyright 2026 Sobware
# License LGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

BOE_OPERATION = object()


class AccountPayment(models.Model):
    _inherit = "account.payment"

    tn_boe = fields.Boolean(
        compute="_compute_tn_boe", store=True, index=True, string="Bill of Exchange"
    )
    boe_reference = fields.Char(copy=False, tracking=True, index=True)
    boe_issue_date = fields.Date(default=fields.Date.context_today, copy=False)
    boe_issue_place = fields.Char(copy=False)
    boe_payment_place = fields.Char(copy=False)
    boe_maturity_date = fields.Date(copy=False, tracking=True, index=True)
    boe_received_date = fields.Date(copy=False)
    boe_acceptance = fields.Selection(
        [("pending", "Pending"), ("accepted", "Accepted"), ("refused", "Refused")],
        default="pending",
        copy=False,
        tracking=True,
    )
    boe_acceptance_date = fields.Date(copy=False)
    boe_signed_document = fields.Binary(attachment=True, copy=False)
    boe_signed_filename = fields.Char(copy=False)
    boe_custody = fields.Selection(
        [
            ("not_received", "Not Received"),
            ("portfolio", "In Portfolio"),
            ("returned", "Returned"),
        ],
        default="not_received",
        copy=False,
        tracking=True,
        index=True,
    )
    boe_user_id = fields.Many2one(
        "res.users",
        string="Follow-up Responsible",
        default=lambda self: self.env.user,
        check_company=True,
        tracking=True,
    )
    boe_next_action = fields.Char(tracking=True)
    boe_next_action_date = fields.Date(tracking=True, index=True)
    boe_last_contact_date = fields.Date(tracking=True)
    boe_promise_date = fields.Date(tracking=True)
    boe_promise_amount = fields.Monetary()
    boe_replaced_payment_id = fields.Many2one(
        "account.payment", check_company=True, copy=False, ondelete="restrict"
    )
    boe_invoice_ids = fields.Many2many(
        "account.move",
        "tn_boe_origin_invoice_rel",
        "payment_id",
        "move_id",
        string="Original Invoices",
        check_company=True,
        copy=False,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
    )
    boe_settlement_ids = fields.One2many("l10n_tn.boe.settlement", "bill_id")
    boe_incident_ids = fields.One2many("l10n_tn.boe.incident", "bill_id")
    boe_source_settlement_id = fields.Many2one(
        "l10n_tn.boe.settlement", copy=False, readonly=True, check_company=True
    )
    boe_active_amount = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="Active Principal"
    )
    boe_pending_amount = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="Pending Collection"
    )
    boe_collected_amount = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="Collected Principal"
    )
    boe_unpaid_amount = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="Returned Principal"
    )
    boe_recovery_amount = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="Recoveries"
    )
    boe_recovery_residual = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="To Recover"
    )
    boe_exposure_amount = fields.Monetary(
        compute="_compute_boe_amounts", store=True, string="Bill Exposure"
    )
    boe_settlement_status = fields.Selection(
        [
            ("draft", "Not Confirmed"),
            ("open", "Not Collected"),
            ("partial", "Partially Collected"),
            ("collected", "Collected"),
            ("unpaid", "Unpaid"),
            ("canceled", "Canceled"),
        ],
        compute="_compute_boe_amounts",
        store=True,
        index=True,
    )
    boe_days_overdue = fields.Integer(compute="_compute_boe_days")
    boe_overdue = fields.Boolean(
        compute="_compute_boe_days", search="_search_boe_overdue"
    )
    boe_available_amount = fields.Monetary(compute="_compute_boe_available")

    _boe_reference_unique = models.Constraint(
        "unique(company_id, partner_id, boe_reference)",
        "This bill reference already exists for this customer and company.",
    )

    @api.model
    def default_get(self, field_names):
        result = super().default_get(field_names)
        if self.env.context.get("tn_boe_creation"):
            method = self.env["account.chart.template"].ref(
                "tn_boe_inbound", raise_if_not_found=False
            )
            if not method:
                raise UserError(
                    self.env._(
                        "Add the bill journal from the company chart settings first."
                    )
                )
            result.update(
                journal_id=method.journal_id.id, payment_method_line_id=method.id
            )
        return result

    @api.depends("payment_method_code")
    def _compute_tn_boe(self):
        for payment in self:
            payment.tn_boe = payment.payment_method_code == "tn_bill_of_exchange"

    @api.depends(
        "tn_boe",
        "state",
        "move_id.line_ids.amount_residual",
        "boe_settlement_ids.state",
        "boe_settlement_ids.amount",
        "boe_incident_ids.state",
        "boe_incident_ids.amount",
        "boe_incident_ids.recovery_residual",
        "boe_incident_ids.recovered_amount",
    )
    def _compute_boe_amounts(self):
        for payment in self:
            active = pending = collected = unpaid = recovery = remaining = 0.0
            status = "draft"
            if payment.tn_boe and payment.move_id.state == "posted":
                liquidity, _counterpart, _writeoff = payment._seek_for_lines()
                active = max(0.0, sum(liquidity.mapped("amount_residual")))
                pending = sum(
                    payment.boe_settlement_ids.filtered(
                        lambda s: s.state == "pending" and not s.incident_id
                    ).mapped("amount")
                )
                incidents = payment.boe_incident_ids.filtered(
                    lambda i: i.state == "posted"
                )
                unpaid = sum(incidents.mapped("amount"))
                remaining = sum(incidents.mapped("recovery_residual"))
                recovery = sum(incidents.mapped("recovered_amount"))
                collected = max(0.0, payment.amount - active - unpaid)
                status = (
                    "unpaid"
                    if unpaid
                    else "collected"
                    if payment.currency_id.is_zero(active)
                    else "partial"
                    if collected
                    else "open"
                )
            if payment.state == "canceled":
                active = pending = collected = 0.0
                status = "canceled"
            payment.boe_active_amount = active
            payment.boe_pending_amount = pending
            payment.boe_collected_amount = collected
            payment.boe_unpaid_amount = unpaid
            payment.boe_recovery_amount = recovery
            payment.boe_recovery_residual = remaining
            payment.boe_exposure_amount = active + remaining
            payment.boe_settlement_status = status

    @api.depends("boe_active_amount", "boe_pending_amount")
    def _compute_boe_available(self):
        for payment in self:
            payment.boe_available_amount = max(
                0.0, payment.boe_active_amount - payment.boe_pending_amount
            )

    @api.depends("boe_maturity_date", "boe_active_amount")
    def _compute_boe_days(self):
        today = fields.Date.context_today(self)
        for payment in self:
            payment.boe_days_overdue = (
                max(0, (today - payment.boe_maturity_date).days)
                if payment.boe_maturity_date and payment.boe_active_amount
                else 0
            )
            payment.boe_overdue = payment.boe_days_overdue > 0

    @api.model
    def _search_boe_overdue(self, operator, value):
        if operator not in ("in", "not in", "=", "!="):
            return NotImplemented
        if operator in ("in", "not in"):
            accepted = set(value)
            if accepted == {True, False} or not accepted:
                all_records = bool(accepted) == (operator == "in")
                return [] if all_records else [("id", "=", 0)]
            wanted = True in accepted
        else:
            wanted = bool(value)
        if operator in ("not in", "!="):
            wanted = not wanted
        domain = [
            ("tn_boe", "=", True),
            ("boe_active_amount", ">", 0),
            ("boe_maturity_date", "<", fields.Date.context_today(self)),
        ]
        return domain if wanted else ["!", "&", "&", *domain]

    def _boe_lock(self):
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()

    def _boe_check_accountant(self, manager=False):
        group = (
            "account.group_account_manager"
            if manager
            else "account.group_account_invoice"
        )
        if not self.env.user.has_group(group):
            raise AccessError(self.env._("An authorized accounting user is required."))
        self.check_access("write")

    @api.constrains(
        "tn_boe",
        "amount",
        "currency_id",
        "company_id",
        "partner_id",
        "payment_type",
        "partner_type",
        "boe_maturity_date",
        "boe_issue_date",
        "boe_invoice_ids",
        "boe_replaced_payment_id",
    )
    def _check_boe(self):
        for payment in self.filtered("tn_boe"):
            if (
                payment.payment_type != "inbound"
                or payment.partner_type != "customer"
                or payment.company_id.chart_template != "tn"
                or payment.currency_id != self.env.ref("base.TND")
                or payment.company_id.currency_id != payment.currency_id
                or payment.currency_id.compare_amounts(payment.amount, 0) <= 0
            ):
                raise ValidationError(
                    self.env._(
                        "Bills require a Tunisian company, a positive TND amount and a "
                        "customer receipt."
                    )
                )
            if (
                payment.boe_maturity_date
                and payment.boe_issue_date
                and payment.boe_maturity_date < payment.boe_issue_date
            ):
                raise ValidationError(
                    self.env._("Maturity cannot precede the issue date.")
                )
            for invoice in payment.boe_invoice_ids:
                if (
                    invoice.state != "posted"
                    or invoice.move_type != "out_invoice"
                    or invoice.company_id != payment.company_id
                    or invoice.commercial_partner_id
                    != payment.partner_id.commercial_partner_id
                    or invoice.currency_id != payment.currency_id
                ):
                    raise ValidationError(
                        self.env._(
                            "Bill invoices must match the customer, company and "
                            "currency."
                        )
                    )
            previous = payment.boe_replaced_payment_id
            if previous and (
                previous == payment
                or not previous.tn_boe
                or previous.company_id != payment.company_id
                or previous.partner_id != payment.partner_id
                or previous.boe_active_amount
                or previous.boe_pending_amount
                or previous.state not in ("rejected", "canceled")
            ):
                raise ValidationError(
                    self.env._(
                        "Return or cancel the previous bill before replacing it."
                    )
                )

    def write(self, vals):
        if self.env.context.get("tn_boe_operation") is BOE_OPERATION:
            return super().write(vals)
        bills = self.filtered("tn_boe")
        linked = self.filtered("boe_source_settlement_id")
        method = self.env["account.payment.method.line"].browse(
            vals.get("payment_method_line_id")
        )
        if method.code == "tn_bill_of_exchange" and self.filtered(
            lambda payment: payment.state != "draft"
        ):
            raise UserError(
                self.env._(
                    "Only a draft payment can be converted into a bill of exchange."
                )
            )
        if {
            "tn_boe",
            "boe_active_amount",
            "boe_pending_amount",
            "boe_collected_amount",
            "boe_unpaid_amount",
            "boe_recovery_amount",
            "boe_recovery_residual",
            "boe_settlement_status",
            "boe_exposure_amount",
            "boe_source_settlement_id",
        }.intersection(vals):
            raise AccessError(
                self.env._(
                    "Bill totals and collection links are managed by accounting "
                    "operations."
                )
            )
        if bills and {
            "state",
            "move_id",
            "boe_custody",
        }.intersection(vals):
            raise UserError(self.env._("Use the bill workflow actions."))
        fixed_fields = {
            "amount",
            "currency_id",
            "partner_id",
            "journal_id",
            "date",
            "company_id",
            "payment_type",
            "partner_type",
            "payment_method_line_id",
            "destination_account_id",
            "outstanding_account_id",
            "boe_reference",
            "boe_maturity_date",
            "boe_issue_date",
            "boe_issue_place",
            "boe_payment_place",
            "boe_received_date",
            "boe_acceptance",
            "boe_acceptance_date",
            "boe_signed_document",
            "boe_invoice_ids",
            "boe_replaced_payment_id",
        }
        if fixed_fields.intersection(vals) and bills.filtered(
            lambda payment: payment.state != "draft"
        ):
            raise UserError(
                self.env._(
                    "Confirmed bill details are locked; reverse the operation before "
                    "correcting it."
                )
            )
        if linked and (fixed_fields | {"state", "move_id"}).intersection(vals):
            raise UserError(
                self.env._("Use the linked bill collection to modify this payment.")
            )
        return super().write(vals)

    @api.constrains(
        "tn_boe", "state", "move_id", "boe_acceptance", "boe_signed_document"
    )
    def _check_boe_payment_state(self):
        for bill in self.filtered("tn_boe"):
            if bill.state in ("in_process", "paid") and (
                not bill.move_id
                or bill.boe_acceptance != "accepted"
                or not bill.boe_signed_document
            ):
                raise ValidationError(
                    self.env._(
                        "A confirmed bill needs an accounting entry and signed "
                        "acceptance."
                    )
                )
            if bill.state == "paid" and not bill.is_matched:
                raise ValidationError(
                    self.env._(
                        "Collect the outstanding principal before marking a bill as "
                        "paid."
                    )
                )

    def _generate_journal_entry(
        self, write_off_line_vals=None, force_balance=None, line_ids=None
    ):
        bills = self.filtered("tn_boe")
        if not bills:
            return super()._generate_journal_entry(
                write_off_line_vals, force_balance, line_ids
            )
        if write_off_line_vals or force_balance is not None or line_ids:
            raise UserError(
                self.env._("Bill receipts do not support custom entries or write-offs.")
            )
        if self.env.context.get("tn_boe_operation") is not BOE_OPERATION:
            bills._boe_check_receipt()
        return super(
            AccountPayment, self.with_context(tn_boe_operation=BOE_OPERATION)
        )._generate_journal_entry()

    def _prepare_move_liquidity_lines(self, default_values):
        result = super()._prepare_move_liquidity_lines(default_values)
        if self.tn_boe:
            for values in result:
                values["date_maturity"] = self.boe_maturity_date
        return result

    def action_post(self):
        bills = self.filtered("tn_boe")
        if not bills:
            return super().action_post()
        bills._boe_check_receipt()
        super(AccountPayment, self - bills).action_post()
        result = super(
            AccountPayment, bills.with_context(tn_boe_operation=BOE_OPERATION)
        ).action_post()
        bills._boe_allocate()
        return result

    def _boe_check_receipt(self):
        self._boe_check_accountant()
        self._boe_lock()
        for bill in self:
            if (
                bill.state not in ("draft", "in_process")
                or bill.boe_custody != "not_received"
                or bill.move_id.state == "posted"
            ):
                raise UserError(self.env._("This bill has already been confirmed."))
            if not all(
                (
                    bill.boe_reference,
                    bill.boe_maturity_date,
                    bill.boe_issue_date,
                    bill.boe_received_date,
                    bill.boe_acceptance == "accepted",
                    bill.boe_acceptance_date,
                    bill.boe_signed_document,
                    bill.boe_user_id,
                    bill.boe_invoice_ids,
                )
            ):
                raise UserError(
                    self.env._(
                        "Complete the reference, dates, acceptance proof, responsible "
                        "and invoices."
                    )
                )
            account = bill.outstanding_account_id
            if (
                not account.reconcile
                or account != bill.payment_method_line_id.payment_account_id
                or account == bill.journal_id.default_account_id
                or account.account_type != "asset_receivable"
                or account == bill.destination_account_id
                or not bill.journal_id.tn_boe_journal
            ):
                raise UserError(
                    self.env._(
                        "Configure a separate reconcilable bills receivable account on"
                        " the bill method."
                    )
                )
            invoices = bill.boe_invoice_ids
            invoices.lock_for_update()
            invoices.line_ids.invalidate_recordset()
            lines = invoices.line_ids.filtered_domain(
                [
                    ("account_id", "=", bill.destination_account_id.id),
                    ("amount_residual", ">", 0),
                ]
            )
            if (
                bill.currency_id.compare_amounts(
                    sum(lines.mapped("amount_residual")), bill.amount
                )
                < 0
            ):
                raise UserError(
                    self.env._("The bill exceeds the remaining invoice balance.")
                )
            bill._boe_check_replacement()

    def _boe_allocate(self):
        for bill in self:
            _liquidity, counterpart, _writeoff = bill._seek_for_lines()
            lines = bill.boe_invoice_ids.line_ids.filtered_domain(
                [
                    ("account_id", "=", bill.destination_account_id.id),
                    ("reconciled", "=", False),
                ]
            )
            if (
                bill.boe_replaced_payment_id
                and bill.boe_replaced_payment_id.state != "canceled"
            ):
                incidents = bill.boe_replaced_payment_id.boe_incident_ids.filtered(
                    lambda incident: incident.recovery_residual > 0
                )
                for incident in incidents:
                    (counterpart + incident.invoice_line_id).with_context(
                        tn_boe_operation=BOE_OPERATION,
                        tn_boe_allocation=(counterpart.id, incident.recovery_residual),
                    ).reconcile()
                    incident.sudo().write(
                        {
                            "replacement_bill_id": bill.id,
                            "replacement_amount": incident.recovery_residual,
                        }
                    )
            else:
                (counterpart + lines).reconcile()
            if any(
                not line.currency_id.is_zero(line.amount_residual)
                for line in counterpart
            ):
                raise UserError(
                    self.env._("The bill must be fully allocated to its invoices.")
                )
            bill.boe_invoice_ids.write({"matched_payment_ids": [Command.link(bill.id)]})
            bill.with_context(tn_boe_operation=BOE_OPERATION).boe_custody = "portfolio"
            bill.message_post(
                body=self.env._(
                    "Signed bill received and allocated to the original invoices."
                )
            )

    def _boe_check_replacement(self):
        self.ensure_one()
        previous = self.boe_replaced_payment_id
        if not previous or previous.state == "canceled":
            return
        previous._boe_lock()
        incidents = previous.boe_incident_ids.filtered(
            lambda incident: incident.recovery_residual > 0
        )
        if (
            not incidents
            or any(incidents.mapped("pending_amount"))
            or self.currency_id.compare_amounts(
                sum(incidents.mapped("recovery_residual")), self.amount
            )
            or set(incidents.invoice_id.ids) != set(self.boe_invoice_ids.ids)
        ):
            raise UserError(
                self.env._(
                    "A replacement must cover exactly the old unpaid invoices and their"
                    " unreserved remaining principal."
                )
            )

    def action_validate(self):
        if self.filtered("tn_boe"):
            raise UserError(
                self.env._("Record and confirm the actual collection to settle a bill.")
            )
        return super().action_validate()

    def action_reject(self):
        if self.filtered("tn_boe"):
            return self.action_boe_operation("unpaid")
        return super().action_reject()

    def action_cancel(self):
        if self.filtered("tn_boe"):
            return self.action_boe_operation("cancel")
        return super().action_cancel()

    def action_draft(self):
        if self.filtered("tn_boe"):
            raise UserError(
                self.env._("Use the cancellation procedure and prepare a new bill.")
            )
        return super().action_draft()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_boe_history(self):
        if self.filtered(
            lambda p: (p.tn_boe or p.boe_source_settlement_id) and p.move_id
        ):
            raise UserError(
                self.env._(
                    "Keep the bill history; reverse posted operations instead of "
                    "deleting them."
                )
            )

    def action_boe_operation(self, operation="collect"):
        self.ensure_one()
        self._boe_check_accountant()
        if not self.tn_boe:
            raise UserError(self.env._("Select a bill of exchange."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Bill Operation"),
            "res_model": "l10n_tn.boe.operation",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_bill_id": self.id,
                "default_operation": operation,
                "default_amount": self.boe_available_amount,
            },
        }

    def action_boe_unpaid(self):
        return self.action_boe_operation("unpaid")

    def action_boe_cancel(self):
        return self.action_boe_operation("cancel")

    def action_boe_spreadsheet(self):
        dashboard = self.env.ref(
            "l10n_tn_account_payment_bill_of_exchange.dashboard_boe"
        )
        return {
            "type": "ir.actions.client",
            "tag": "action_spreadsheet_dashboard",
            "params": {"dashboard_id": dashboard.id},
        }

    @api.model
    def _cron_boe_followup(self):
        bills = self.search(
            [
                ("tn_boe", "=", True),
                "|",
                ("boe_active_amount", ">", 0),
                ("boe_recovery_residual", ">", 0),
            ]
        )
        today = fields.Date.context_today(self)
        activity_type = self.env.ref(
            "l10n_tn_account_payment_bill_of_exchange.activity_boe"
        )
        closed = self.search(
            [
                ("tn_boe", "=", True),
                ("boe_active_amount", "=", 0),
                ("boe_recovery_residual", "=", 0),
                ("state", "!=", "draft"),
                ("activity_ids.activity_type_id", "=", activity_type.id),
            ]
        )
        closed.activity_feedback(
            ["l10n_tn_account_payment_bill_of_exchange.activity_boe"],
            feedback=self.env._("Bill follow-up completed: no remaining principal."),
        )
        for bill in bills:
            reasons = bill._boe_followup_reasons(today)
            if not reasons:
                continue
            existing = bill.activity_ids.filtered(
                lambda a: a.activity_type_id == activity_type
            )
            user = bill.boe_user_id or bill.company_id.tn_boe_manager_id
            if existing:
                escalation = today - timedelta(
                    days=bill.company_id.tn_boe_escalation_days
                )
                if (
                    min(existing.mapped("date_deadline")) < escalation
                    and bill.company_id.tn_boe_manager_id
                ):
                    existing.user_id = bill.company_id.tn_boe_manager_id
                continue
            if user:
                bill.activity_schedule(
                    "l10n_tn_account_payment_bill_of_exchange.activity_boe",
                    date_deadline=today,
                    user_id=user.id,
                    summary=self.env._("Bill follow-up"),
                    note="\n".join(reasons),
                )

    def _boe_followup_reasons(self, today):
        self.ensure_one()
        reasons = []
        if self.boe_active_amount and self.boe_maturity_date <= today + timedelta(
            days=self.company_id.tn_boe_reminder_days
        ):
            reasons.append(self.env._("Bill maturity requires follow-up."))
        if self.boe_pending_amount:
            reasons.append(self.env._("Confirm the pending collection."))
        if self.boe_recovery_residual:
            reasons.append(self.env._("Recover the unpaid principal."))
        if self.boe_promise_date and self.boe_promise_date < today:
            reasons.append(self.env._("The promised payment date has passed."))
        if self.boe_next_action_date and self.boe_next_action_date <= today:
            reasons.append(self.boe_next_action or self.env._("Follow-up action due."))
        return reasons
