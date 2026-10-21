"use client";

import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";

const STORAGE_KEY = "ar-theme";

type ThemeContextValue = {
  choice: ThemeChoice;
  setChoice: (choice: ThemeChoice) => void;
};

const ThemeContext = createContext<ThemeContextValue>({
  choice: "system",
  setChoice: () => undefined,
});

function applyTheme(choice: ThemeChoice) {
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = choice === "dark" || (choice === "system" && systemDark);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.dataset.theme = choice;
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>("system");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const next: ThemeChoice = stored === "light" || stored === "dark" ? stored : "system";
    setChoiceState(next);
    applyTheme(next);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const current = window.localStorage.getItem(STORAGE_KEY);
      if (current !== "light" && current !== "dark") {
        applyTheme("system");
      }
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  function setChoice(next: ThemeChoice) {
    window.localStorage.setItem(STORAGE_KEY, next);
    setChoiceState(next);
    applyTheme(next);
  }

  return <ThemeContext.Provider value={{ choice, setChoice }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
