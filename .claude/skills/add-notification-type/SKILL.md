---
name: add-notification-type
description: Add a new NotificationType end-to-end — enum value, a fan-out helper in app/services/notifications.py, the call site that invokes it, and the React Email template. Use when the user asks to "add a notification", "wire up an email for X", "send an email when Y happens", or otherwise introduces a new admin/customer notification event.
---

# Add a new NotificationType

Notifications fan out through `app/core/event_bus.py` into the arq worker
(`task_send_notification` in `app/worker.py`), which writes the in-app
`Notification` row and delivers email via Resend using hosted templates keyed by
the event type. **All publish calls live in `app/services/notifications.py`** —
routers/repositories just `await notify_<event>(...)` from there. Adding a
notification touches the enum, that service module, the call site, and a
template. (Background: [[edenscale-notification-architecture]].)

## Step 1 — Pick the audience

- **Customer** (`CustomerNotificationType`) — a single recipient (an investor
  contact, an invitee, the assigned user). Uses `publish_customer_event`. This
  is the common case in edenscale.
- **Admin** (`AdminNotificationType`) — an org-level event fanned out to every
  **manager** of the org (roles admin/fund_manager/superadmin, via
  `UserOrganizationMembership`). Uses `publish_admin_event(db, ...)`.

There are **no webhooks and no i18n** in edenscale — ignore those parts of the
speed original. Email is the only delivery channel.

## Step 2 — Add the enum member

Edit `backend/app/models/enums.py`, adding to `AdminNotificationType` or
`CustomerNotificationType` (both are `enum.StrEnum`). snake_case symbol,
`<audience>.<event_slug>` value:

```python
class CustomerNotificationType(enum.StrEnum):
    ...
    CAPITAL_CALL = "customer.capital_call"
```

The string value is load-bearing: with non-alphanumerics stripped it becomes the
Resend template id (`customer.capital_call` → `customercapitalcall`, see
`app/services/channels/email_channel.py`).

## Step 3 — Add a helper in `app/services/notifications.py`

Add `async def notify_<event_slug>(db, *, ...)`. The helper:

1. Reads already-persisted ORM objects (an org/fund/entity + the recipient).
2. Builds a **flat snake_case `payload`** — scalars only (pre-format money with
   `_fmt_money`, dates with `_fmt_date`; never pass raw Decimals/dates). This
   becomes the Resend variable bag via `_flatten_variables`.
3. Calls `publish_customer_event` (single recipient) and/or `publish_admin_event`
   (manager fan-out), passing `organization_id` so the worker auto-attaches org
   branding (`organization_name`, `organization_slug`, `organization_website`).
4. Is wrapped in `try/except Exception: logger.exception(...)` — fire-and-forget.

Recipient rules:
- Pass `user_id=str(contact.user_id)` when the contact has a linked user (→ in-app
  row **and** email), or `user_id=None` for an email-only recipient (invitation to
  a non-user); put the address in `data["recipient_email"]`.
- For fan-outs over investor contacts, reuse `_primary_contact_rows` /
  `_recipient_user_id`.

```python
async def notify_capital_call(db: Session, *, call: CapitalCall) -> None:
    try:
        fund = db.query(Fund).filter(Fund.id == call.fund_id).first()
        organization = db.query(Organization).filter(
            Organization.id == fund.organization_id).first()
        for item, commitment, investor, contact in _primary_contact_rows(
            db, CapitalCallItem, CapitalCallItem.capital_call_id, call.id
        ):
            await publish_customer_event(
                user_id=_recipient_user_id(contact),
                organization_id=str(organization.id),
                event_type=CustomerNotificationType.CAPITAL_CALL,
                title=f"Capital call: {call.title} — {fund.name}",
                message=f"A capital call for {call.title} has been issued.",
                data={"recipient_email": contact.email, "amount_due":
                      _fmt_money(item.amount_due, fund.currency_code), ...},
                reference_type="capital_call",
                reference_id=str(call.id),
            )
    except Exception:
        logger.exception("Capital-call %s notify fan-out failed", call.id)
```

## Step 3b — Call the helper from the trigger site

After the row is committed, add a single `await notify_<event_slug>(db, ...)` in
the router handler (make it `async`) or repository method. Never call
`publish_*` anywhere outside `notifications.py` — future readers grep `notify_`
to find every place a notification fires.

## Step 4 — Create the email template

Add a `.tsx` under `apps/emails/emails/customer/` or `.../admin/`, named after
the event slug (without the `customer.`/`admin.` prefix):
`customer.capital_call` → `emails/customer/capital_call.tsx`. The file path
determines the Resend template id (non-alphanumerics stripped), which must match
what `email_channel.py` derives — do not deviate from the directory layout.

Copy an existing template. Rules:
- Import from `@/layout/Shell`; wrap content in `<Shell>` and pass
  `organizationName="{{{organization_name}}}"` and
  `organizationWebsite="{{{organization_website}}}"`.
- No prop interface / no default args — everything is a Resend `{{{ key }}}`
  placeholder scraped from the rendered HTML. Keys must match the `data` payload.
- Wrap placeholders in `{"{{{key}}}"}` inside JSX text; raw `"{{{key}}}"` inside
  string attributes. Export a `subject` and a default component.
- edenscale payloads are all pre-formatted strings, so `NUMBER_KEYS` in
  `apps/emails/scripts/push-templates.mts` stays empty — only add a key there if
  a payload sends a raw int/float.

## Step 5 — Wire it into `app/scripts/try_notify.py`

Add: the `notify_*` import, a `_send_<event_slug>(db)` that loads fixtures via the
`_first_*` loaders (add a new one if needed) and awaits the helper, and a
`DISPATCH` entry keyed by the raw enum value. Verify with
`uv run python -m app.scripts.try_notify --list`.

## Step 6 — Tell the user to push the template

The template isn't live until pushed. End with (verbatim, correct path):

> Template needs to be pushed to Resend before it can send. Run:
> ```
> cd apps/emails && RESEND_API_KEY=... pnpm push emails/<audience>/<event_slug>.tsx
> ```
> Then test end-to-end (arq worker must be running — `make start-worker`):
> ```
> cd apps/backend && uv run python -m app.scripts.try_notify <audience>.<event_slug>
> ```

The push script removes any existing same-named template, then creates and
publishes a fresh one. The user runs it so the production Resend account is
touched only with intent.

## Quick checklist

- [ ] Enum member in `backend/app/models/enums.py` with `admin.`/`customer.` prefix
- [ ] `notify_<event_slug>` in `app/services/notifications.py` — `try/except`, flat-scalar payload, `organization_id` passed
- [ ] Helper awaited from the trigger site (handler made `async` if needed)
- [ ] No `publish_*` calls outside `notifications.py`
- [ ] Template `.tsx` under `apps/emails/emails/<audience>/`, placeholders match payload keys, Shell org props passed
- [ ] Dispatcher + `_first_*` loader in `app/scripts/try_notify.py`
- [ ] Told the user the exact `pnpm push` + `try_notify` commands
