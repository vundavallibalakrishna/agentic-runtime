import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Bot,
  Brain,
  CheckCheck,
  Gauge,
  Library,
  MessageSquare,
  Monitor,
  Play,
  Radio,
  Repeat,
  Shield,
  Sparkles,
  Wrench,
} from "lucide-react";

export type NavItem = {
  href: string;
  labelKey:
    | "navChat"
    | "navAgents"
    | "navTools"
    | "navKnowledge"
    | "navMemory"
    | "navSkills"
    | "navRoutines"
    | "navChannels"
    | "navUsage"
    | "navQuotas"
    | "navApprovals"
    | "navRuns"
    | "navModels"
    | "navUsers"
    | "navComputers";
  section: "workspace" | "resources" | "manage";
  permission: string;
  icon: LucideIcon;
  soon?: boolean;
};

export const primaryNav: NavItem[] = [
  {
    href: "/chat",
    section: "workspace",
    labelKey: "navChat",
    permission: "chat:use",
    icon: MessageSquare,
  },
  {
    href: "/agents",
    section: "workspace",
    labelKey: "navAgents",
    permission: "agents:read",
    icon: Bot,
  },
  {
    href: "/tools",
    section: "resources",
    labelKey: "navTools",
    permission: "tools:read",
    icon: Wrench,
  },
  {
    href: "/knowledge",
    section: "resources",
    labelKey: "navKnowledge",
    permission: "knowledge:read",
    icon: Library,
  },
  {
    href: "/memory",
    section: "resources",
    labelKey: "navMemory",
    permission: "chat:use",
    icon: Brain,
  },
  {
    href: "/skills",
    section: "resources",
    labelKey: "navSkills",
    permission: "skills:read",
    icon: Sparkles,
  },
  {
    href: "/routines",
    section: "workspace",
    labelKey: "navRoutines",
    permission: "routines:create",
    icon: Repeat,
  },
  {
    href: "/admin/channels",
    section: "manage",
    labelKey: "navChannels",
    permission: "channels:manage",
    icon: Radio,
  },
  {
    href: "/admin/usage",
    section: "manage",
    labelKey: "navUsage",
    permission: "usage:read",
    icon: BarChart3,
  },
  {
    href: "/admin/quotas",
    section: "manage",
    labelKey: "navQuotas",
    permission: "usage:read",
    icon: Gauge,
  },
  {
    href: "/approvals",
    section: "manage",
    labelKey: "navApprovals",
    permission: "approvals:decide",
    icon: CheckCheck,
  },
  { href: "/runs", section: "manage", labelKey: "navRuns", permission: "chat:use", icon: Play },
  {
    href: "/admin/models",
    section: "manage",
    labelKey: "navModels",
    permission: "models:read",
    icon: Shield,
  },
  {
    href: "/admin/sandboxes",
    section: "manage",
    labelKey: "navComputers",
    permission: "sandboxes:manage",
    icon: Monitor,
  },
  {
    href: "/admin/users",
    section: "manage",
    labelKey: "navUsers",
    permission: "users:read",
    icon: Shield,
  },
];
