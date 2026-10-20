/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const pageSchema = z.object({ "items": z.array(z.record(z.string(), z.any())).optional(), "nextCursor": z.union([z.string(), z.null()]).default(null), "hasMore": z.boolean().default(false) }).strict().describe("Cursor page. Conventions §4, with camelCase keys.\n\nItems are JSON objects. A recursive ``JsonValue`` schema is too deep for the\ngenerated Zod client, and list endpoints return objects.")
