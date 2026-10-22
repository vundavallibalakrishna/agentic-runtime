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
  permission: string;
  icon: LucideIcon;
  soon?: boolean;
};

export const primaryNav: NavItem[] = [
  { href: "/chat", labelKey: "navChat", permission: "chat:use", icon: MessageSquare },
  { href: "/agents", labelKey: "navAgents", permission: "agents:read", icon: Bot },
  { href: "/tools", labelKey: "navTools", permission: "tools:read", icon: Wrench },
  {
    href: "/knowledge",
    labelKey: "navKnowledge",
    permission: "knowledge:read",
    icon: Library,
  },
  { href: "/memory", labelKey: "navMemory", permission: "chat:use", icon: Brain },
  { href: "/skills", labelKey: "navSkills", permission: "skills:read", icon: Sparkles },
  {
    href: "/routines",
    labelKey: "navRoutines",
    permission: "routines:create",
    icon: Repeat,
  },
  {
    href: "/admin/channels",
    labelKey: "navChannels",
    permission: "channels:manage",
    icon: Radio,
  },
  { href: "/admin/usage", labelKey: "navUsage", permission: "usage:read", icon: BarChart3 },
  { href: "/admin/quotas", labelKey: "navQuotas", permission: "usage:read", icon: Gauge },
  {
    href: "/approvals",
    labelKey: "navApprovals",
    permission: "approvals:decide",
    icon: CheckCheck,
  },
  { href: "/runs", labelKey: "navRuns", permission: "chat:use", icon: Play },
  { href: "/admin/models", labelKey: "navModels", permission: "models:read", icon: Shield },
  {
    href: "/admin/sandboxes",
    labelKey: "navComputers",
    permission: "sandboxes:manage",
    icon: Monitor,
  },
  { href: "/admin/users", labelKey: "navUsers", permission: "users:read", icon: Shield },
];
