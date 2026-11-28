/** Route inventory shared by layout checks; contains no customer records or identity. */
export const managementScreens = [
  ["/tools", "Tools"],
  ["/knowledge", "Knowledge"],
  ["/memory", "Memory"],
  ["/skills", "Skills"],
  ["/routines", "Routines"],
  ["/admin/channels", "Channels"],
  ["/approvals", "Approvals"],
  ["/runs", "Runs"],
  ["/admin/models", "Models"],
  ["/admin/sandboxes", "Computers"],
  ["/admin/usage", "Usage"],
  ["/admin/quotas", "Quotas"],
  ["/admin/users", "Users"],
  ["/admin/policies", "Policies"],
  ["/reviews", "Reviews"],
  ["/connections", "Connections"],
] as const;

export const primaryScreens = [
  ...managementScreens,
  ["/chat", "Chat"],
  ["/agents", "Agents"],
  ["/agents/new", "New agent"],
  ["/settings", "Settings"],
  ["/settings/profile", "Profile"],
  ["/connectors", "Connectors"],
  ["/documents", "Documents"],
  ["/inbox", "Inbox"],
  ["/schedules", "Schedules"],
  ["/admin/evals", "Evaluation library"],
  ["/platform/health", "Platform health"],
] as const;
