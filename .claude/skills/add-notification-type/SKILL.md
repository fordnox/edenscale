---
name: add-notification-type
description: Add a new NotificationType end-to-end — enum value, a fan-out helper in app/services/notifications.py, the call site that invokes it, and the React Email template. Use when the user asks to "add a notification", "wire up an email for X", "send an email when Y happens", or otherwise introduces a new admin/customer notification event.
---

# Add a new NotificationType

This codebase fans notifications out through `app/core/event_bus.py` into the arq worker (`task_send_notification`), which delivers via Resend using hosted templates keyed by the event type. **All publish calls live in `app/services/notifications.py`** — repositories and routers stay focused on their own concerns and just `await notify_<event>(...)` from there. Adding a new notification touches the enum, that service module, the call site, and a template.

## Step 1 — Pick the audience

Every notification is **either** admin- or customer-facing. Ask yourself:

- **Admin** (`AdminNotificationType`) — org-level event, fanned out to every admin of the org **and** the org webhook. Use for "ops needs to know" events: a booking was created, a cancellation came in, a group inquiry landed.
- **Customer** (`CustomerNotificationType`) — single-user event, no webhook. Use for "the user we just acted on behalf of needs to know": receipt, status update on their inquiry, expiring membership.

If unsure, lean toward the audience whose mailbox the email will actually land in. A single logical event (e.g. "group booking inquiry") often produces **two** notifications — one admin, one customer — and that is fine; they each get their own enum member and their own template.

## Step 2 — Add the enum member

Edit `backend/app/models/enums.py` and add a member to `AdminNotificationType` or `CustomerNotificationType`. Use snake_case for the symbol and `<audience>.<event_slug>` for the string value:

```python
class AdminNotificationType(StrEnum):
    ...
    BOOKING_REFUND_REQUESTED = "admin.booking_refund_requested"

class CustomerNotificationType(StrEnum):
    ...
    PAYMENT_RECEIPT = "customer.payment_receipt"
```

The string value is load-bearing: it ends up in the DB (`notification_logs.notification_type`), in webhook payloads, and — with non-alphanumerics stripped — as the Resend template id (`admin.booking_refund_requested` → `adminbookingrefundrequested`). See `app/services/channels/email_channel.py:53`.

## Step 3 — Add a helper in `app/services/notifications.py`

`app/services/notifications.py` is the **only** place that calls `publish_admin_event` / `publish_customer_event`. Repositories and routers never call them directly — they `await notify_<event>(...)` from this module so the payload shape, localization, and `try/except` are all in one place.

Add a new `async def notify_<event_slug>(...)` next to `notify_booking_confirmed`. The helper:

1. Takes already-persisted ORM objects + the active `Site` and `User`.
2. Builds the flat snake_case `payload` (see "Shaping the `data` payload" below).
3. Fires `publish_admin_event` and/or `publish_customer_event` from `app.core.event_bus` — usually both, paired with the matching enum members from step 2.
4. Wraps the body in `try/except Exception: logger.exception(...)` so callers can fire-and-forget; notification failures never break the originating write.
5. Localizes user-facing strings (rig name, package name, etc.) with `app.core.i18n.localize_for_user` before they hit the payload.

```python
# app/services/notifications.py

async def notify_booking_refund_requested(
    db: Session,
    *,
    booking: Booking,
    site: Site,
    user: User,
) -> None:
    try:
        rig_name = localize_for_user(
            booking.rig.name if booking.rig else {}, user, default=""
        )
        payload = {
            "booking_id": str(booking.id),
            "rig": rig_name,
            "slot_start": booking.start_time.isoformat(),
            # ...flat scalars only — see rules below
        }
        await publish_admin_event(
            db,
            organization_id=str(site.organization_id),
            event_type=AdminNotificationType.BOOKING_REFUND_REQUESTED,
            title=f"Refund requested: {rig_name}",
            message=f"{user.name} asked for a refund.",
            data=payload,
            reference_type="booking",
            reference_id=str(booking.id),
        )
    except Exception:
        logger.exception("Booking %s refund-notify fan-out failed", booking.id)
```

### Shaping the `data` payload

`data` becomes the Resend template variable bag (via `_flatten_variables` in `app/services/channels/email_channel.py`). Rules:

- **Flat scalars only.** Resend templates can't iterate or branch — strings and numbers are the only first-class types. Dicts are flattened with dot-notation keys (`organization` → `organization.company_name`, etc.), lists are JSON-stringified.
- **Snake_case keys**, no spaces, no periods (periods would collide with the flattener's dotted dict expansion).
- **Pre-format anything conditional.** If the template needs "Peak" vs "Off-peak", or "Refund issued" vs "Refund pending", compute the label in Python and pass it as a single string — never expect the template to choose.
- **The `organization` field is auto-attached** by `task_send_notification` in `app/worker.py` whenever `organization_id` is provided. The Shell branding variables (`organization_company_name`, `organization_company_address`, `organization_company_phone`, `organization_slug`) come for free — do not duplicate them in `data`.

## Step 3b — Call the helper from the trigger site

Find the spot where the event becomes durable — the repository method or router handler that just persisted the row this notification is reporting on. Add a single `await notify_<event_slug>(...)` **after** the commit succeeds.

The natural call sites in this codebase are:

- **Inside a repository method**, after the row is committed (see `CheckoutSessionRepository._finalize_bookings`). The method needs to be `async`; cascade the `async` upward through any chain of internal callers until it reaches an async router handler.
- **Inside a router handler**, after `repo.<action>()` returns (see `routers/user/group_booking_inquiries.py::create_group_booking_inquiry`).

Pick whichever owns the moment the event semantically happens. Do not call publishers anywhere else — even if it feels DRY for a one-off, future readers should be able to grep `notify_` to find every place a notification fires.

```python
from app.services.notifications import notify_booking_refund_requested

# ...repository or router body, after the commit...
await notify_booking_refund_requested(
    db, booking=booking, site=site, user=current_user
)
```

## Step 4 — Create the email template

Add a `.tsx` file under `emails/emails/admin/` or `emails/emails/customer/` named after the event slug (without the `admin.` / `customer.` prefix). Example: `customer.payment_receipt` → `emails/emails/customer/payment_receipt.tsx`.

The file path determines the Resend template id: separators and non-alphanumerics are stripped (`emails/customer/payment_receipt.tsx` → `customerpaymentreceipt`). This must match what `email_channel.py` derives from the event string, so do not deviate from the directory layout.

Template skeleton (copy from `emails/emails/customer/group_booking_inquiry_status_change.tsx` for customer events or `emails/emails/admin/booking_new.tsx` for admin events):

```tsx
import { Section, Text } from "@react-email/components";
import * as React from "react";
import { Shell, h1, p, kicker, MetaRow, MetaDivider, panel, BRAND } from "@/layout/Shell";

// Expected variables (must match the data payload published in step 3):
//   <list every key here>

export const subject = () =>
  "Subject line with {{{some_var}}}";

export default function PaymentReceipt() {
  return (
    <Shell
      preview="Preview line · {{{some_var}}}"
      kickerText="Receipt · {{{receipt_id}}}"
      organizationName="{{{organization_company_name}}}"
      organizationAddress="{{{organization_company_address}}}"
      organizationPhone="{{{organization_company_phone}}}"
      organizationSlug="{{{organization_slug}}}"
    >
      <Text style={h1}>Headline.</Text>
      <Text style={p}>Body referencing {"{{{driver_name}}}"} and so on.</Text>
      {/* MetaRow / panel blocks as needed */}
    </Shell>
  );
}
```

Template rules:

- **No default-arg props, no typed prop interface.** Everything is a Resend `{{{ key }}}` placeholder. The component is rendered once at push time with `Component({})`, and the keys are scraped out of the resulting HTML — local React state would just be lost.
- **Always pass the four organization Shell props** so the header logo, footer name/address/phone reflect the customer's org branding.
- **Wrap placeholders in `{"{{{key}}}"}` when they sit inside JSX text** (so JSX doesn't try to parse the braces as an expression). They can be used raw inside string attributes like `value="{{{x}}}"`.
- **Add new numeric keys to `NUMBER_KEYS`** in `emails/scripts/push-templates.mts` — anything not in that set is registered as a string variable on Resend, and a Resend template-variable type mismatch will reject the email at send time.

## Step 5 — Wire the new type into `app/scripts/try_notify.py`

`backend/app/scripts/try_notify.py` is the ad-hoc tester — it fires any registered notification through the real event bus using the first matching DB rows, so the developer can verify the template renders without having to manually create the trigger condition (a real booking, a real signup, etc.). Every new notification gets a dispatcher entry here, otherwise `try_notify --list` will not see it.

Add three things:

1. **Import the helper** at the top alongside the other `notify_*` imports.
2. **Write a `_send_<event_slug>(db)` async function** that loads the required fixtures using the existing `_first_*` loaders (`_first_organization`, `_first_user_in_org`, `_first_site`, `_first_booking`, `_first_gift_voucher`, `_first_group_inquiry`) and awaits the helper. If your notification needs an entity none of those loaders cover (e.g. a `Membership`, `LoyaltyTransaction`), add a new `_first_<entity>(db, organization_id)` loader next to them — same shape: order by `created_at`, raise `FixtureMissing(...)` if no row exists.
3. **Add the enum value as a key in `DISPATCH`** pointing at your `_send_*` function. If the helper publishes both an admin and a customer event (like `notify_booking_confirmed`), map both enum strings to the same dispatcher.

```python
# app/scripts/try_notify.py

from app.services.notifications import (
    ...
    notify_booking_refund_requested,
)

async def _send_booking_refund_requested(db: Session) -> None:
    org = _first_organization(db)
    booking, site, user = _first_booking(db, str(org.id))
    await notify_booking_refund_requested(db, booking=booking, site=site, user=user)

DISPATCH: dict[str, Callable[[Session], Awaitable[None]]] = {
    ...
    "admin.booking_refund_requested": _send_booking_refund_requested,
}
```

Verify with `cd backend && uv run python -m app.scripts.try_notify --list` — your new value should appear in the alphabetical output.

## Step 6 — Tell the user to push the template

The template is not live on Resend until it is pushed. End the work by telling the user (verbatim, with the correct path):

> Template needs to be pushed to Resend before it can be sent. Run:
> ```
> cd emails && RESEND_API_KEY=... npm run push emails/<audience>/<event_slug>.tsx
> ```
>
> Then test it end-to-end with:
> ```
> cd backend && uv run python -m app.scripts.try_notify <audience>.<event_slug>
> ```
> (the arq worker must be running — `make start-worker` — for the email to actually leave the box.)

The push script (`emails/scripts/push-templates.mts`) removes any existing template with the same name, then creates and publishes a fresh one. The user must do this themselves so the production Resend account is touched only with intent.

## Quick checklist

- [ ] Enum member added in `backend/app/models/enums.py` with `admin.` / `customer.` prefix
- [ ] `notify_<event_slug>` helper added to `app/services/notifications.py`, internal `try/except`, localized strings, flat-scalar payload
- [ ] Helper awaited from the trigger site (repository post-commit or router after `repo.x()`), `async` propagated upward if needed
- [ ] No direct `publish_admin_event` / `publish_customer_event` calls outside `app/services/notifications.py`
- [ ] Template `.tsx` file under `emails/emails/<audience>/` with all four `organization_*` Shell props
- [ ] Any new numeric variables added to `NUMBER_KEYS` in `emails/scripts/push-templates.mts`
- [ ] Dispatcher entry added in `backend/app/scripts/try_notify.py` (`_send_*` function + `DISPATCH` key); new `_first_*` loader if the notification needs an entity not yet covered
- [ ] Told the user the exact `npm run push` command and the matching `try_notify` invocation
