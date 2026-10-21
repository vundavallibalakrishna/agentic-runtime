"use client";

import { useTheme } from "@/components/theme-provider";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { choice, setChoice } = useTheme();
  const next = choice === "dark" ? "light" : "dark";
  return (
    <Button onClick={() => setChoice(next)} type="button" variant="outline">
      {choice === "dark" ? "Light" : "Dark"}
    </Button>
  );
}
