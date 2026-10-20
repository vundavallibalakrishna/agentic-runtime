"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  return (
    <Button type="button" variant="outline" onClick={() => setDark((value) => !value)}>
      {dark ? "Light" : "Dark"}
    </Button>
  );
}
