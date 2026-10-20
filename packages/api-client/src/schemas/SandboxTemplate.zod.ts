/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const sandboxTemplateSchema = z.object({ "imageRef": z.string(), "runtimeClass": z.enum(["gvisor","kata"]).default("gvisor"), "cpuMillis": z.number().int().gte(1), "memoryMb": z.number().int().gte(1), "diskGb": z.number().int().gte(1), "allowBrowser": z.boolean().default(false), "egressAllowlist": z.array(z.string()).optional(), "maxClassification": z.string().default("internal"), "idleSuspendS": z.number().int().gte(1).default(900), "maxLifetimeS": z.number().int().gte(1).default(86400), "execTimeoutS": z.number().int().gte(1).default(300), "retentionDays": z.number().int().gte(1).default(7) }).strict()
