/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const skillSchema = z.object({ "description": z.string(), "visibility": z.enum(["private","team","tenant"]).default("tenant"), "requiredTools": z.array(z.string()).optional(), "instructionsMd": z.string(), "assets": z.array(z.object({ "path": z.string(), "file": z.string() }).strict()).optional() }).strict()
