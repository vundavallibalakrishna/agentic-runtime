export type Definition = {
  persona?: { displayName?: string; greeting?: string };
  instructions?: string;
  starterPrompts?: string[];
  model?: { alias?: string; fastAlias?: string };
  tools?: { server?: string; version?: string; include?: string[] }[];
  budget?: { maxSteps?: number; maxTokens?: number };
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
