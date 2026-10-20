/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const sandboxTemplateSchema = z.object({ "image_ref": z.string(), "runtime_class": z.enum(["gvisor","kata"]).default("gvisor"), "cpu_millis": z.number().int().gte(1), "memory_mb": z.number().int().gte(1), "disk_gb": z.number().int().gte(1), "allow_browser": z.boolean().default(false), "egress_allowlist": z.array(z.string()).optional(), "max_classification": z.string().default("internal"), "idle_suspend_s": z.number().int().gte(1).default(900), "max_lifetime_s": z.number().int().gte(1).default(86400), "exec_timeout_s": z.number().int().gte(1).default(300), "retention_days": z.number().int().gte(1).default(7) }).strict()
