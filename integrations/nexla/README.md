# Nexla Integration — Data Ingestion & Normalization

**Status: designed, endpoint live.** V1 demos with a mock inbox; the app already
exposes the webhook Nexla delivers to, so switching to live data is config-only.

## Flow design

```
Gmail / IMAP  ──►  Nexla Flow  ──►  Webhook Destination  ──►  POST /api/ingest
(raw email)        (normalize)      (this app, local)         (extractor agent)
```

## Nexla flow configuration

1. **Source**: Email connector (IMAP) on the demo mailbox — incremental sync,
   Nexla handles threading, dedup, and attachment metadata.
2. **Transform**: map raw messages to the CPOS normalized schema:

```json
{
  "message_id": "$.headers.message-id",
  "thread_id":  "$.thread.id",
  "from":       "$.from.address",
  "to":         "$.to[0].address",
  "date":       "$.date",
  "subject":    "$.subject",
  "body":       "$.text_body"
}
```

3. **Destination**: Webhook → `https://<tunnel>/api/ingest` (local app exposed
   via cloudflared/ngrok, keeping storage local-first).

The mock inbox (`data/sample_emails.json`) uses the exact same schema, so the
downstream agents don't change at all when live data is switched on.
