import type { LucideIcon } from "lucide-react";
import {
  Bot,
  CheckCheck,
  Library,
  MessageSquare,
  Play,
  Repeat,
  Shield,
  Wrench,
} from "lucide-react";

export type NavItem = {
  href: string;
  labelKey:
    | "navChat"
    | "navAgents"
    | "navTools"
    | "navKnowledge"
    | "navRoutines"
    | "navApprovals"
    | "navRuns"
    | "navModels"
    | "navUsers";
  permission: string;
  icon: LucideIcon;
  soon?: boolean;
};

export const primaryNav: NavItem[] = [
  { href: "/chat", labelKey: "navChat", permission: "chat:use", icon: MessageSquare },
  { href: "/agents", labelKey: "navAgents", permission: "agents:read", icon: Bot },
  { href: "/tools", labelKey: "navTools", permission: "tools:read", icon: Wrench, soon: true },
  {
    href: "/knowledge",
    labelKey: "navKnowledge",
    permission: "knowledge:read",
    icon: Library,
    soon: true,
  },
  {
    href: "/routines",
    labelKey: "navRoutines",
    permission: "routines:create",
    icon: Repeat,
    soon: true,
  },
  {
    href: "/approvals",
    labelKey: "navApprovals",
    permission: "approvals:decide",
    icon: CheckCheck,
    soon: true,
  },
  { href: "/runs", labelKey: "navRuns", permission: "chat:use", icon: Play, soon: true },
  { href: "/admin/models", labelKey: "navModels", permission: "models:read", icon: Shield },
  { href: "/admin/users", labelKey: "navUsers", permission: "users:read", icon: Shield },
];
