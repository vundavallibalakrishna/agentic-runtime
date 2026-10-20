import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { AppShell } from "@/components/app-shell";
import { UiGallery } from "@/components/ui-gallery";

const meta = {
  title: "Shell/AppShell",
  component: AppShell,
} satisfies Meta<typeof AppShell>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { children: <UiGallery /> },
};
