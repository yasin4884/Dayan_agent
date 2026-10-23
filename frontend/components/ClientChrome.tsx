"use client";

import { AgentBubble } from "@/components/AgentBubble";
import { OnboardingTour } from "@/components/OnboardingTour";

/** کلاینت‌شل سراسری — تا usePathname داخل layout سرور گیر نکند. */
export function ClientChrome() {
  return (
    <>
      <OnboardingTour />
      <AgentBubble />
    </>
  );
}
