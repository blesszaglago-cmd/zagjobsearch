"use client";

import type { ReactNode } from "react";
import { openCookieSettings } from "@/lib/cookie-consent";

export default function CookieSettingsButton({
  children = "Cookie settings",
  className = "cookie-text-button",
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <button type="button" className={className} onClick={openCookieSettings}>
      {children}
    </button>
  );
}
