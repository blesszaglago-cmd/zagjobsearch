"use client";
import { readCookieChoice } from "./cookie-consent";

export const measurementId = "G-3N6T2M5ED8";
type AnalyticsWindow = Window & {
  dataLayer?: unknown[];
  gtag?: (...args: unknown[]) => void;
  "ga-disable-G-3N6T2M5ED8"?: boolean;
};
export function analyticsAllowed() {
  return readCookieChoice() === "granted";
}

export function disableAnalytics() {
  const analytics = window as AnalyticsWindow;
  analytics[`ga-disable-${measurementId}`] = true;
  // Only remove this site's analytics cookies; never touch sign-in cookies.
  try {
    for (const cookie of document.cookie.split(";")) {
      const name = cookie.trim().split("=")[0];
      if (name !== "_ga" && !/^_ga_[A-Za-z0-9_]+$/.test(name)) continue;
      for (const domain of [
        "",
        `; Domain=${location.hostname}`,
        `; Domain=.${location.hostname}`,
      ]) {
        document.cookie = `${name}=; Max-Age=0; Path=/${domain}; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
      }
    }
  } catch {
    // Some privacy settings block cookie access. Collection remains disabled.
  }
}

export function initialiseAnalytics() {
  if (!analyticsAllowed()) {
    disableAnalytics();
    return;
  }
  const analytics = window as AnalyticsWindow;
  const wasDisabled = analytics[`ga-disable-${measurementId}`] === true;
  analytics[`ga-disable-${measurementId}`] = false;
  if (!analytics.gtag) {
    analytics.dataLayer = analytics.dataLayer || [];
    analytics.gtag = function () {
      // eslint-disable-next-line prefer-rest-params
      analytics.dataLayer!.push(arguments);
    };
    analytics.gtag("consent", "default", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    analytics.gtag("consent", "update", { analytics_storage: "granted" });
    analytics.gtag("js", new Date());
    analytics.gtag("config", measurementId, {
      send_page_view: false,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      cookie_domain: location.hostname,
      cookie_expires: 60 * 60 * 24 * 180,
      cookie_update: false,
      cookie_flags:
        location.protocol === "https:" ? "SameSite=Lax;Secure" : "SameSite=Lax",
      page_location: location.origin,
      page_referrer: "",
    });
    const script = document.createElement("script");
    script.id = "zag-google-analytics";
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
    document.head.appendChild(script);
  } else if (wasDisabled) {
    analytics.gtag("consent", "update", { analytics_storage: "granted" });
  }
  return analytics;
}
type PublicEvent =
  | "apply_click"
  | "save_application"
  | "sign_up"
  | "login"
  | "share_job"
  | "save_search";
export function trackEvent(
  name: PublicEvent,
  details: Record<string, string> = {},
) {
  try {
    const analytics = initialiseAnalytics();
    if (!analytics) return;
    analytics.gtag?.("event", name, {
      ...details,
      page_location: location.origin,
      page_referrer: "",
      page_title: "Job seeker action",
    });
  } catch {
    /* Optional analytics never blocks an action. */
  }
}
