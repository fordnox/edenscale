---
title: Documents and communications
description: Which documents an investor can access, how confidentiality works, and how letters and read receipts behave.
---

## Documents

`GET /documents` (filterable by fund, investor, and document type) and `GET /documents/{id}` apply a three-way visibility rule for LPs. A document is visible when **any** of these hold:

1. It is scoped to an **investor entity** the LP is a linked contact for (KYC packs, subscription documents, investor-specific notices).
2. The LP **uploaded it themselves**.
3. It is a **non-confidential fund document** on a fund the LP holds a commitment in (quarterly reports, fund notices).

Fund documents flagged **confidential** are hidden from LPs entirely — they exist only for the manager side.

### Uploads

File transfer is split from record creation:

- `POST /documents/upload-init` and `PUT /documents/upload/{key}` (≤ 100 MB) are available to **any authenticated user**, including LPs — this is how a contact can push a file (e.g. signed subscription docs) to storage.
- Creating the actual document record (`POST /documents`), editing (`PATCH /{id}`), and deleting (`DELETE /{id}`) are manager-only; the API answers `403 Only admins and fund managers can create documents` for LPs.

When a document is attached for an investor, linked contacts receive a `customer.document_uploaded` notification.

## Communications (letters and announcements)

Communications are manager-authored messages (`announcement`, `message`, `notification` types) addressed to recipients either directly by user or via **investor contact** rows — which is how LPs receive them.

- `GET /communications` (filterable by `fund_id` and `type`) and `GET /funds/{fund_id}/communications` list communications where the LP is a recipient (directly or through a linked contact) or the sender. Drafts they are not on stay invisible.
- `GET /communications/{id}` returns `403` unless the LP is a recipient.

### Read receipts

`POST /communications/{id}/recipients/{recipient_id}/read` is the one write an investor has here: marking **their own** recipient row as read (sets `read_at`). Attempting to acknowledge someone else's row returns `403 Cannot mark another recipient's row as read`. Fund managers see these receipts as delivery confirmation.

Creating, editing, and sending communications (`POST`, `PATCH /{id}`, `POST /{id}/send`) are manager-only. Sending fans out `customer.communication` notifications to recipients.
