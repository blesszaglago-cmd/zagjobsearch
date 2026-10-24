"use client";

export const consentCookie = "zag_cookie_consent";
export const consentMaxAge = 60 * 60 * 24 * 180;
const changeEvent = "zag-cookie-consent";
const settingsEvent = "zag-cookie-settings";
const syncKey = "zag_cookie_consent_sync";
export type CookieChoice = "granted" | "denied" | null;
let pageChoice: string | undefined;

export function parseConsent(
  value: string | undefined,
  now = Date.now(),
): CookieChoice {
  const match = /^v1\.(granted|denied)\.(\d{13})$/.exec(value || "");
  if (!match) return null;
  const age = now - Number(match[2]);
  return age >= 0 && age < consentMaxAge * 1000
    ? (match[1] as Exclude<CookieChoice, null>)
    : null;
}

function storedConsent() {
  try {
    return document.cookie
      .split(";")
      .map((entry) => entry.trim())
      .find((entry) => entry.startsWith(`${consentCookie}=`))
      ?.slice(consentCookie.length + 1);
  } catch {
    return undefined;
  }
}

export function readCookieChoice(): CookieChoice {
  if (typeof document === "undefined") return null;
  return parseConsent(pageChoice ?? storedConsent());
}

export function saveCookieChoice(value: Exclude<CookieChoice, null>) {
  const encoded = `v1.${value}.${Date.now()}`;
  try {
    document.cookie = `${consentCookie}=${encoded}; Max-Age=${consentMaxAge}; Path=/; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  } catch {
    // A blocked cookie must not prevent someone from using the site.
  }
  const persisted = storedConsent() === encoded;
  pageChoice = persisted ? undefined : encoded;
  try {
    // This signal synchronizes other tabs; it never grants consent on its own.
    localStorage.setItem(syncKey, encoded);
    localStorage.removeItem("zag_analytics_consent_v1");
  } catch {}
  window.dispatchEvent(new Event(changeEvent));
  return persisted;
}

export function subscribeCookieChoice(callback: () => void) {
  const sync = (event?: Event) => {
    // Only a persisted choice from another tab can replace a page-only fallback.
    if (event?.type === "storage") {
      const changed = event as StorageEvent;
      if (changed.key === syncKey && changed.newValue === storedConsent())
        pageChoice = undefined;
    }
    callback();
  };
  window.addEventListener("storage", sync);
  window.addEventListener("focus", sync);
  window.addEventListener(changeEvent, sync);
  document.addEventListener("visibilitychange", sync);
  const timer = window.setInterval(sync, 60_000);
  return () => {
    window.removeEventListener("storage", sync);
    window.removeEventListener("focus", sync);
    window.removeEventListener(changeEvent, sync);
    document.removeEventListener("visibilitychange", sync);
    window.clearInterval(timer);
  };
}

export function openCookieSettings() {
  window.dispatchEvent(new Event(settingsEvent));
}

export function subscribeCookieSettings(callback: () => void) {
  window.addEventListener(settingsEvent, callback);
  return () => window.removeEventListener(settingsEvent, callback);
}
