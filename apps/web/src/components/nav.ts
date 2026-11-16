import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  CalendarClock,
  CheckCheck,
  ClipboardCheck,
  FileText,
  Gauge,
  Inbox,
  Library,
  Link2,
  MessageSquare,
  Monitor,
  Play,
  Plug,
  Radio,
  Repeat,
  Settings,
  Shield,
  Sparkles,
  Wrench,
} from "lucide-react";

export type NavItem = {
  href: string;
  labelKey:
    | "navChat"
    | "navConnectors"
    | "navCatalog"
    | "navSettings"
    | "navAgents"
    | "navTools"
    | "navDocuments"
    | "navKnowledge"
    | "navMemory"
    | "navSkills"
    | "navRoutines"
    | "navSchedules"
    | "navInbox"
    | "navChannels"
    | "navUsage"
    | "navQuotas"
    | "navEvals"
    | "navHealth"
    | "navApprovals"
    | "navRuns"
    | "navModels"
    | "navUsers"
    | "navComputers";
  section: "work" | "build" | "data" | "admin";
  permission: string;
  /** A tenant feature flag that must be on for the item to show. */
  feature?: string;
  icon: LucideIcon;
  soon?: boolean;
};

export const primaryNav: NavItem[] = [
  {
    href: "/chat",
    section: "work",
    labelKey: "navChat",
    permission: "chat:use",
    icon: MessageSquare,
  },
  {
    href: "/agents",
    section: "build",
    labelKey: "navAgents",
    permission: "agents:read",
    icon: Bot,
  },
  {
    href: "/tools",
    section: "build",
    labelKey: "navTools",
    permission: "tools:read",
    icon: Wrench,
  },
  {
    href: "/documents",
    section: "data",
    labelKey: "navDocuments",
    permission: "chat:use",
    icon: FileText,
  },
  {
    href: "/connectors",
    section: "data",
    labelKey: "navCatalog",
    permission: "tools:read",
    icon: Plug,
  },
  {
    href: "/connections",
    section: "data",
    labelKey: "navConnectors",
    permission: "connections:manage_own",
    icon: Link2,
  },
  {
    href: "/settings/profile",
    section: "admin",
    labelKey: "navSettings",
    permission: "chat:use",
    icon: Settings,
  },
  {
    href: "/knowledge",
    section: "data",
    labelKey: "navKnowledge",
    permission: "knowledge:read",
    icon: Library,
  },
  {
    href: "/memory",
    section: "data",
    labelKey: "navMemory",
    permission: "chat:use",
    icon: Brain,
  },
  {
    href: "/skills",
    section: "build",
    labelKey: "navSkills",
    permission: "skills:read",
    icon: Sparkles,
  },
  {
    href: "/routines",
    section: "build",
    labelKey: "navRoutines",
    permission: "routines:create",
    icon: Repeat,
  },
  {
    href: "/schedules",
    section: "build",
    labelKey: "navSchedules",
    permission: "routines:create",
    icon: CalendarClock,
  },
  {
    href: "/inbox",
    section: "work",
    labelKey: "navInbox",
    permission: "chat:use",
    icon: Inbox,
  },
  {
    href: "/admin/channels",
    section: "admin",
    labelKey: "navChannels",
    permission: "channels:manage",
    icon: Radio,
  },
  {
    href: "/admin/evals",
    section: "admin",
    labelKey: "navEvals",
    permission: "evals:manage",
    icon: ClipboardCheck,
  },
  {
    href: "/platform/health",
    section: "admin",
    labelKey: "navHealth",
    permission: "usage:read",
    icon: Activity,
  },
  {
    href: "/admin/usage",
    section: "admin",
    labelKey: "navUsage",
    permission: "usage:read",
    icon: BarChart3,
  },
  {
    href: "/admin/quotas",
    section: "admin",
    labelKey: "navQuotas",
    permission: "usage:read",
    icon: Gauge,
  },
  {
    href: "/approvals",
    section: "work",
    labelKey: "navApprovals",
    permission: "approvals:decide",
    icon: CheckCheck,
  },
  { href: "/runs", section: "work", labelKey: "navRuns", permission: "chat:use", icon: Play },
  {
    href: "/admin/models",
    section: "admin",
    labelKey: "navModels",
    permission: "models:read",
    icon: Shield,
  },
  {
    href: "/admin/sandboxes",
    section: "admin",
    labelKey: "navComputers",
    permission: "sandboxes:manage",
    icon: Monitor,
  },
  {
    href: "/admin/users",
    section: "admin",
    labelKey: "navUsers",
    permission: "users:read",
    icon: Shield,
  },
];
