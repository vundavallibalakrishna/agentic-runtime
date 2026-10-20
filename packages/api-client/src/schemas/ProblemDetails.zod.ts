/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const problemDetailsSchema = z.object({ "type": z.string(), "title": z.string(), "status": z.number().int(), "code": z.string(), "detail": z.string(), "instance": z.string(), "requestId": z.string(), "errors": z.array(z.object({ "loc": z.array(z.union([z.string(), z.number().int()])), "msg": z.string(), "type": z.string() }).strict().describe("One entry in a problem ``errors`` array.")).optional() }).strict().describe("RFC 9457 body. ``code`` values stay snake_case; the key is ``requestId``.")
