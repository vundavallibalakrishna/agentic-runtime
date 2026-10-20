/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const dataConnectionSchema = z.object({ "engine": z.literal("postgres").default("postgres"), "dsn_secret": z.string(), "identity_mode": z.enum(["service","per_user_mapped","passthrough"]).default("service"), "allowlist_schemas": z.array(z.string()).optional(), "allowlist_tables": z.array(z.string()).optional(), "columns_deny": z.array(z.string()).optional(), "row_limit": z.number().int().gte(1).default(1000), "statement_timeout_s": z.number().int().gte(1).default(30), "classification": z.string().default("internal"), "schema_notes": z.string().default("") }).strict()
