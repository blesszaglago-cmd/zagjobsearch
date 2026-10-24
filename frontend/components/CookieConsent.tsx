"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";

import { disableAnalytics, initialiseAnalytics } from "@/lib/analytics";
import {
  readCookieChoice,
  saveCookieChoice,
  subscribeCookieChoice,
  subscribeCookieSettings,
  type CookieChoice,
} from "@/lib/cookie-consent";
import CookieSettingsButton from "./CookieSettingsButton";

const serverChoice = () => undefined;

export default function CookieConsent() {
  const choice = useSyncExternalStore(
    subscribeCookieChoice,
    readCookieChoice,
    serverChoice,
  );
  const dialog = useRef<HTMLDialogElement>(null);
  const [analyticsEnabled, setAnalyticsEnabled] = useState(false);
  const [message, setMessage] = useState("");
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

  useEffect(
    () =>
      subscribeCookieSettings(() => {
        setAnalyticsEnabled(readCookieChoice() === "granted");
        if (!dialog.current?.open) dialog.current?.showModal();
      }),
    [],
  );

  useEffect(() => {
    if (choice === undefined) return;
    if (choice !== "granted") {
      disableAnalytics();
      return;
    }
    const analytics = initialiseAnalytics();
    if (!analytics?.gtag || !publicPage) return;
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

  function choose(value: Exclude<CookieChoice, null>) {
    // Disable immediately, including while a previously loaded tag is pending.
    if (value === "denied") disableAnalytics();
    const persisted = saveCookieChoice(value);
    dialog.current?.close();
    setMessage(
      persisted
        ? "Your cookie preferences have been saved."
        : "Your browser could not save this choice. It applies to this page only.",
    );
  }

  return (
    <>
      <div className="cookie-controls">
        <CookieSettingsButton />
        <span className="cookie-status" role="status">
          {message}
        </span>
      </div>
      {choice === null ? (
        <section
          className="cookie-banner"
          aria-labelledby="cookie-banner-title"
        >
          <div className="cookie-banner-copy">
            <span className="cookie-eyebrow">Your privacy, your choice</span>
            <h2 id="cookie-banner-title">A few cookies. Always your call.</h2>
            <p>
              Essential cookies keep sign-in secure and remember your
              preferences. With your permission, optional analytics helps us
              improve the site. You can search, create an account and apply with
              either choice. <Link href="/cookies">Read our cookie policy</Link>
              .
            </p>
          </div>
          <div className="cookie-banner-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => choose("granted")}
            >
              Accept all
            </button>
            <button
              type="button"
              className="btn-outline"
              onClick={() => choose("denied")}
            >
              Reject optional
            </button>
            <CookieSettingsButton className="cookie-text-button">
              Manage preferences
            </CookieSettingsButton>
          </div>
        </section>
      ) : null}
      <dialog
        ref={dialog}
        className="cookie-dialog"
        aria-labelledby="cookie-dialog-title"
        aria-describedby="cookie-dialog-description"
      >
        <div className="cookie-dialog-heading">
          <div>
            <span className="cookie-eyebrow">jobs.ac.ghana</span>
            <h2 id="cookie-dialog-title">Cookie preferences</h2>
          </div>
          <button
            type="button"
            className="cookie-close"
            aria-label="Close cookie preferences"
            onClick={() => dialog.current?.close()}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path d="m6 6 12 12M18 6 6 18" />
            </svg>
          </button>
        </div>
        <p id="cookie-dialog-description">
          Choose what you share. Optional cookies are off until you accept them.
          You can change your choice at any time.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            choose(analyticsEnabled ? "granted" : "denied");
          }}
        >
          <div className="cookie-category">
            <div className="cookie-category-heading">
              <h3>Essential cookies</h3>
              <span className="cookie-required">Always on</span>
            </div>
            <p>
              Keep your account signed in securely, protect sign-in and remember
              this choice. These cookies are needed for the site to work.
            </p>
          </div>
          <div className="cookie-category">
            <div className="cookie-category-heading">
              <label htmlFor="cookie-analytics">Optional analytics</label>
              <input
                id="cookie-analytics"
                className="cookie-toggle"
                type="checkbox"
                role="switch"
                checked={analyticsEnabled}
                onChange={(event) => setAnalyticsEnabled(event.target.checked)}
                aria-describedby="cookie-analytics-description"
              />
            </div>
            <p id="cookie-analytics-description">
              Google Analytics measures public page visits and actions such as
              Apply clicks. We exclude your name, email, search keywords and
              private application contents. We do not use advertising cookies.
            </p>
          </div>
          <p className="cookie-preference-note">
            Your choice lasts up to six months on this browser. Turning
            analytics off clears its cookies without signing you out.{" "}
            <Link href="/cookies">Cookie policy</Link> ·{" "}
            <Link href="/privacy">Privacy policy</Link>
          </p>
          <div className="cookie-dialog-actions">
            <button
              type="button"
              className="btn-outline"
              onClick={() => choose("denied")}
            >
              Reject optional
            </button>
            <button type="submit" className="btn-primary">
              Save preferences
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
