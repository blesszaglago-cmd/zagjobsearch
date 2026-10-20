"use client";
export const measurementId = "G-3N6T2M5ED8";
type AnalyticsWindow = Window & {
  dataLayer?: unknown[];
  gtag?: (...args: unknown[]) => void;
};
export function analyticsAllowed() {
  try {
    return localStorage.getItem("zag_analytics_consent_v1") === "granted";
  } catch {
    return false;
  }
}
export function initialiseAnalytics() {
  if (!analyticsAllowed()) return;
  const analytics = window as AnalyticsWindow;
  if (!analytics.gtag) {
    analytics.dataLayer = analytics.dataLayer || [];
    analytics.gtag = function () {
      // eslint-disable-next-line prefer-rest-params
      analytics.dataLayer!.push(arguments);
    };
    analytics.gtag("consent", "default", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    analytics.gtag("js", new Date());
    analytics.gtag("config", measurementId, {
      send_page_view: false,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      cookie_domain: location.hostname,
      cookie_expires: 60 * 60 * 24 * 180,
      cookie_update: false,
      page_location: location.origin,
      page_referrer: "",
    });
    const script = document.createElement("script");
    script.id = "zag-google-analytics";
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
    document.head.appendChild(script);
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
