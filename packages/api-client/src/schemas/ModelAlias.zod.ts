/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const modelAliasSchema = z.object({ "kind": z.enum(["chat","embed","rerank"]), "primaryModel": z.string(), "fallbackModels": z.array(z.string()).optional() }).strict()
