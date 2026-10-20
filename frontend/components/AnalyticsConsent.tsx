"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";

import { measurementId, initialiseAnalytics } from "@/lib/analytics";
const storageKey = "zag_analytics_consent_v1";
const changeEvent = "zag-analytics-consent";
type Choice = "granted" | "denied" | null;
type AnalyticsWindow = Window & {
  dataLayer?: unknown[];
  gtag?: (...args: unknown[]) => void;
  "ga-disable-G-3N6T2M5ED8"?: boolean;
};

function readChoice(): Choice {
  try {
    const value = localStorage.getItem(storageKey);
    return value === "granted" || value === "denied" ? value : null;
  } catch {
    return null;
  }
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(changeEvent, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(changeEvent, callback);
  };
}

function clearAnalyticsCookies() {
  const hostname = location.hostname;
  for (const cookie of document.cookie.split(";")) {
    const name = cookie.trim().split("=")[0];
    if (name !== "_ga" && !name.startsWith("_ga_")) continue;
    for (const domain of [
      "",
      `; Domain=${hostname}`,
      `; Domain=.${hostname}`,
    ]) {
      document.cookie = `${name}=; Max-Age=0; Path=/${domain}; SameSite=Lax; Secure`;
    }
  }
}

export default function AnalyticsConsent() {
  const choice = useSyncExternalStore(subscribe, readChoice, () => null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const pathname = usePathname();
  const publicPage =
    pathname === "/" ||
    pathname === "/search" ||
    pathname.startsWith("/jobs/") ||
    pathname.startsWith("/regions/") ||
    [
      "/privacy",
      "/terms",
      "/cookies",
      "/sources",
      "/about",
      "/sponsor",
    ].includes(pathname);

  useEffect(() => {
    const analytics = window as AnalyticsWindow;
    analytics[`ga-disable-${measurementId}`] = choice !== "granted";
    if (choice !== "granted") return;

    initialiseAnalytics();
    if (!analytics.gtag || !publicPage) return;
    let referrer = "";
    try {
      referrer = new URL(document.referrer).origin;
    } catch {}
    const campaign =
      new URLSearchParams(window.location.search).get("utm_source") || "";
    const source = [
      "whatsapp",
      "telegram",
      "campus",
      "linkedin",
      "newsletter",
    ].includes(campaign)
      ? campaign
      : undefined;
    analytics.gtag("event", "page_view", {
      page_location: location.origin + pathname,
      page_referrer: referrer,
      ...(source ? { campaign_source: source } : {}),
      page_title:
        pathname === "/"
          ? "jobs.ac.ghana"
          : pathname.startsWith("/jobs/")
            ? "Job details | jobs.ac.ghana"
            : `${pathname.slice(1)} | jobs.ac.ghana`,
    });
  }, [choice, pathname, publicPage]);

  function choose(value: Exclude<Choice, null>) {
    const analytics = window as AnalyticsWindow;
    analytics[`ga-disable-${measurementId}`] = value !== "granted";
    try {
      localStorage.setItem(storageKey, value);
    } catch {
      /* Keep the site usable when storage is unavailable. */
    }
    if (value === "denied") {
      clearAnalyticsCookies();
      // Reload unloads any previously accepted Google script and event listeners.
      if (analytics.gtag) {
        location.reload();
        return;
      }
    }
    window.dispatchEvent(new Event(changeEvent));
    setSettingsOpen(false);
  }

  return (
    <>
      <div className="analytics-settings">
        <button type="button" onClick={() => setSettingsOpen(true)}>
          Analytics settings
        </button>
      </div>
      {choice === null || settingsOpen ? (
        <section
          className="analytics-banner"
          aria-label="Analytics preferences"
        >
          <div>
            <h2>Help improve jobs.ac.ghana</h2>
            <p>
              Allow optional Google Analytics to measure visits to public pages.
              Your private application records stay out of analytics.{" "}
              <Link href="/cookies">Cookie details</Link>
            </p>
          </div>
          <div className="analytics-actions">
            <button
              type="button"
              className="btn-outline"
              onClick={() => choose("denied")}
            >
              Decline analytics
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => choose("granted")}
            >
              Allow analytics
            </button>
            {choice !== null ? (
              <button
                type="button"
                className="text-action"
                onClick={() => setSettingsOpen(false)}
              >
                Close
              </button>
            ) : null}
          </div>
        </section>
      ) : null}
    </>
  );
}
