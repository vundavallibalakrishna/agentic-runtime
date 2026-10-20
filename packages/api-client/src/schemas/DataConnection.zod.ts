/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const dataConnectionSchema = z.object({ "engine": z.literal("postgres").default("postgres"), "dsnSecret": z.string(), "identityMode": z.enum(["service","per_user_mapped","passthrough"]).default("service"), "allowlistSchemas": z.array(z.string()).optional(), "allowlistTables": z.array(z.string()).optional(), "columnsDeny": z.array(z.string()).optional(), "rowLimit": z.number().int().gte(1).default(1000), "statementTimeoutS": z.number().int().gte(1).default(30), "classification": z.string().default("internal"), "schemaNotes": z.string().default("") }).strict()
