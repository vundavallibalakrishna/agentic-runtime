export type Definition = {
  persona?: { displayName?: string; greeting?: string };
  instructions?: string;
  starterPrompts?: string[];
  model?: { alias?: string; fastAlias?: string };
  tools?: {
    server?: string;
    version?: string;
    include?: string[];
    overrides?: Record<
      string,
      {
        timeoutS?: number;
        maxOutputBytes?: number;
        maxFileBytes?: number;
        network?: boolean;
        allowHosts?: string[];
        rowLimit?: number;
        schemas?: string[];
        tables?: string[];
      }
    >;
  }[];
  output?: { jsonSchema?: Record<string, unknown> };
  skills?: string[];
  knowledge?: { collections?: string[] };
  subagents?: {
    allowed?: string[];
    maxDepth?: number;
    maxParallel?: number;
    allowSelfClone?: boolean;
    childTimeoutS?: number;
  };
  human?: { enabled?: boolean };
  contract?: {
    description?: string;
    inputSchema?: Record<string, unknown>;
    outputSchema?: Record<string, unknown>;
  };
  budget?: {
    maxSteps?: number;
    maxTokens?: number;
    maxCostMicros?: number;
    maxWallClockS?: number;
    maxToolCalls?: number;
  };
};

export type AgentSummary = {
  id: string;
  slug: string;
  name: string;
  description?: string;
  greeting?: string;
  status?: string;
  visibility?: string;
  owner?: { displayName?: string };
  publishedVersion?: number | null;
  draftVersion?: number | null;
  favourite?: boolean;
  starterPrompts?: string[];
  builtin?: boolean;
  etag?: string;
  canEdit?: boolean;
  disabled?: boolean;
};

export type AgentDetail = AgentSummary & {
  draft?: { id?: string; definition?: Definition; version?: number; etag?: string } | null;
  published?: { id?: string; definition?: Definition; version?: number } | null;
};

export type ValidationReport = {
  valid?: boolean;
  errors?: { msg?: string; type?: string }[];
  warnings?: { msg?: string; type?: string }[];
};
