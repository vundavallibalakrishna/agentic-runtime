/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. Do not edit. */
import { z } from "zod"

export const channelIntegrationSchema = z.object({ "kind": z.enum(["slack","teams","email","widget"]), "secret": z.string(), "default_agent": z.string(), "config": z.record(z.string(), z.string()).optional() }).strict()
