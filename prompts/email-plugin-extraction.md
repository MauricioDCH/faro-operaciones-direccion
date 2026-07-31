# Faro email plugin extraction

Version: 1.0.0

Use the connected Gmail app/integration in read-only mode.

Search only the dedicated synthetic Faro account using the query supplied by the user. Process only messages matching that query.

Classify each message as one of:
- `new_order`
- `quantity_change`
- `cancellation`
- `delivery_update`
- `supplier_notice`
- `unknown`

Extract only evidence-supported fields. Never invent IDs, dates, products, quantities, URLs, or source references. Use `null` when unknown.

Return one JSON object matching:
`schemas/plugin-email-batch.schema.json`

Requirements:
- output raw JSON only;
- no Markdown fences or commentary;
- include platform, plugin/app, query, prompt version, generation time, and limitations;
- preserve the source citation, link, or locator exposed by the integration;
- keep `body_excerpt` and `evidence_excerpt` minimal;
- confidence must be between 0 and 1;
- set uncertain extractions to `review_status: "pending"`;
- do not send, modify, archive, label, or delete email;
- do not process non-synthetic messages;
- report unavailable references in `limitations`.
