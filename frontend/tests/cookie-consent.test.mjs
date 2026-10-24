import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

function browser({
  blockedCookies = false,
  blockedStorage = false,
  throwCookieAccess = false,
  initialCookies = {},
} = {}) {
  let clock = Date.UTC(2026, 9, 24, 14);
  const cookies = new Map(Object.entries(initialCookies));
  const writes = [];
  const scripts = [];
  const storage = new Map();
  const timers = new Set();
  const document = new EventTarget();
  document.head = { appendChild: (script) => scripts.push(script) };
  document.createElement = () => ({});
  Object.defineProperty(document, "cookie", {
    get: () => {
      if (throwCookieAccess) throw Error("Cookie access blocked");
      return [...cookies].map(([key, value]) => `${key}=${value}`).join("; ");
    },
    set: (value) => {
      if (throwCookieAccess) throw Error("Cookie access blocked");
      writes.push(value);
      if (blockedCookies) return;
      const pair = value.split(";")[0];
      const index = pair.indexOf("=");
      const name = pair.slice(0, index);
      if (/Max-Age=0(?:;|$)/.test(value)) cookies.delete(name);
      else cookies.set(name, pair.slice(index + 1));
    },
  });
  const window = new EventTarget();
  window.setInterval = (callback) => {
    timers.add(callback);
    return callback;
  };
  window.clearInterval = (callback) => timers.delete(callback);
  const location = {
    protocol: "https:",
    hostname: "site.example",
    origin: "https://site.example",
  };
  const localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => {
      if (blockedStorage) throw Error("Storage blocked");
      storage.set(key, value);
    },
    removeItem: (key) => {
      if (blockedStorage) throw Error("Storage blocked");
      storage.delete(key);
    },
  };
  class Clock extends Date {
    static now() {
      return clock;
    }
  }
  const cache = new Map();
  function load(name) {
    if (cache.has(name)) return cache.get(name);
    const filename = fileURLToPath(
      new URL(`../lib/${name}.ts`, import.meta.url),
    );
    const code = ts.transpileModule(readFileSync(filename, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    }).outputText;
    const module = { exports: {} };
    cache.set(name, module.exports);
    vm.runInNewContext(
      code,
      {
        module,
        exports: module.exports,
        require: (path) => {
          assert.equal(path, "./cookie-consent");
          return load("cookie-consent");
        },
        document,
        window,
        location,
        localStorage,
        Event,
        Date: Clock,
      },
      { filename },
    );
    return module.exports;
  }
  return {
    consent: load("cookie-consent"),
    analytics: load("analytics"),
    cookies,
    writes,
    scripts,
    storage,
    window,
    timers,
    now: () => clock,
    advance: (milliseconds) => {
      clock += milliseconds;
      for (const tick of timers) tick();
    },
    externalChoice: (choice) => {
      const value = `v1.${choice}.${clock}`;
      cookies.set("zag_cookie_consent", value);
      window.dispatchEvent(
        Object.assign(new Event("storage"), {
          key: "zag_cookie_consent_sync",
          newValue: value,
        }),
      );
    },
  };
}

test("new visitors and legacy grants cannot load analytics before a new choice", () => {
  const b = browser();
  b.storage.set("zag_analytics_consent_v1", "granted");
  b.storage.set("zag_cookie_consent_sync", `v1.granted.${b.now()}`);
  assert.equal(b.consent.readCookieChoice(), null);
  assert.equal(b.analytics.analyticsAllowed(), false);
  b.analytics.trackEvent("apply_click");
  assert.equal(b.scripts.length, 0);
  assert.equal(b.window["ga-disable-G-3N6T2M5ED8"], true);
});

test("malformed, unknown-version, future and expired preferences never grant analytics", () => {
  const b = browser();
  const { parseConsent, consentMaxAge } = b.consent;
  const now = b.now();
  for (const value of [
    undefined,
    "granted",
    "v2.granted.1792846800000",
    `v1.unknown.${now}`,
    `v1.granted.${now + 1}`,
    `v1.granted.${now - consentMaxAge * 1000}`,
  ]) {
    assert.equal(parseConsent(value, now), null);
  }
  assert.equal(parseConsent(`v1.granted.${now}`, now), "granted");
  assert.equal(parseConsent(`v1.denied.${now}`, now), "denied");
});

test("both choices use a host-only secure 180-day cookie and preserve account cookies", () => {
  for (const choice of ["granted", "denied"]) {
    const b = browser({ initialCookies: { zag_session: "test-only-session" } });
    b.storage.set("zag_analytics_consent_v1", "granted");
    assert.equal(b.consent.saveCookieChoice(choice), true);
    assert.equal(b.consent.readCookieChoice(), choice);
    assert.match(
      b.writes[0],
      /^zag_cookie_consent=v1\.(granted|denied)\.\d{13}; Max-Age=15552000; Path=\/; SameSite=Lax; Secure$/,
    );
    assert.doesNotMatch(b.writes[0], /Domain=|test-only-session/);
    assert.equal(b.cookies.get("zag_session"), "test-only-session");
    assert.equal(b.storage.has("zag_analytics_consent_v1"), false);
  }
});

test("explicit consent loads one tag with denied advertising and sanitized configuration", () => {
  const b = browser();
  b.consent.saveCookieChoice("granted");
  b.analytics.initialiseAnalytics();
  b.analytics.trackEvent("share_job");
  b.analytics.initialiseAnalytics();
  assert.equal(b.scripts.length, 1);
  assert.equal(
    b.scripts[0].src,
    "https://www.googletagmanager.com/gtag/js?id=G-3N6T2M5ED8",
  );
  const commands = b.window.dataLayer.map((args) => Array.from(args));
  assert.equal(commands[0][0], "consent");
  assert.equal(commands[0][2].analytics_storage, "denied");
  for (const key of ["ad_storage", "ad_user_data", "ad_personalization"])
    assert.equal(commands[0][2][key], "denied");
  assert.equal(commands[1][1], "update");
  assert.equal(commands[1][2].analytics_storage, "granted");
  const config = commands.find((command) => command[0] === "config")[2];
  assert.equal(config.send_page_view, false);
  assert.equal(config.allow_google_signals, false);
  assert.equal(config.allow_ad_personalization_signals, false);
  assert.equal(config.cookie_domain, "site.example");
  assert.equal(config.cookie_expires, b.consent.consentMaxAge);
  assert.equal(config.cookie_update, false);
  assert.equal(config.cookie_flags, "SameSite=Lax;Secure");
  assert.equal(config.page_location, "https://site.example");
  assert.equal(config.page_referrer, "");
});

test("withdrawal stops events and clears only analytics cookies without reloading", () => {
  const b = browser({
    initialCookies: {
      zag_session: "test-only-session",
      zag_pkce: "test-only-verifier",
      _ga: "test-only-ga",
      _ga_3N6T2M5ED8: "test-only-ga-session",
      other_preference: "keep",
    },
  });
  b.consent.saveCookieChoice("granted");
  b.analytics.initialiseAnalytics();
  const previousEvents = b.window.dataLayer.length;
  b.analytics.disableAnalytics();
  b.consent.saveCookieChoice("denied");
  b.analytics.trackEvent("apply_click");
  assert.equal(b.window["ga-disable-G-3N6T2M5ED8"], true);
  assert.equal(b.window.dataLayer.length, previousEvents);
  assert.equal(b.cookies.has("_ga"), false);
  assert.equal(b.cookies.has("_ga_3N6T2M5ED8"), false);
  assert.equal(b.cookies.get("zag_session"), "test-only-session");
  assert.equal(b.cookies.get("zag_pkce"), "test-only-verifier");
  assert.equal(b.cookies.get("other_preference"), "keep");
  assert.equal(b.consent.readCookieChoice(), "denied");
  b.consent.saveCookieChoice("granted");
  b.analytics.trackEvent("share_job");
  assert.equal(b.window["ga-disable-G-3N6T2M5ED8"], false);
  assert.equal(b.scripts.length, 1);
  assert.equal(b.window.dataLayer.at(-1)[1], "share_job");
});

test("expiry stops events and notifies an already open page", () => {
  const b = browser();
  b.consent.saveCookieChoice("granted");
  b.analytics.initialiseAnalytics();
  let observed;
  const unsubscribe = b.consent.subscribeCookieChoice(() => {
    observed = b.consent.readCookieChoice();
  });
  b.advance(b.consent.consentMaxAge * 1000);
  assert.equal(observed, null);
  const previousEvents = b.window.dataLayer.length;
  b.analytics.trackEvent("share_job");
  assert.equal(b.window.dataLayer.length, previousEvents);
  assert.equal(b.window["ga-disable-G-3N6T2M5ED8"], true);
  unsubscribe();
  assert.equal(b.timers.size, 0);
});

test("saved changes synchronize across tabs and subscriptions clean up", () => {
  const b = browser();
  let calls = 0;
  let observed;
  const unsubscribe = b.consent.subscribeCookieChoice(() => {
    calls++;
    observed = b.consent.readCookieChoice();
  });
  b.externalChoice("granted");
  assert.equal(observed, "granted");
  b.externalChoice("denied");
  assert.equal(observed, "denied");
  b.analytics.trackEvent("apply_click");
  assert.equal(b.scripts.length, 0);
  unsubscribe();
  b.externalChoice("granted");
  assert.equal(calls, 2);
  assert.equal(b.timers.size, 0);
});

test("blocked cookies and localStorage allow a page-only choice without exceptions", () => {
  const b = browser({ blockedCookies: true, blockedStorage: true });
  const unsubscribe = b.consent.subscribeCookieChoice(() => {});
  assert.equal(b.consent.saveCookieChoice("granted"), false);
  assert.equal(b.consent.readCookieChoice(), "granted");
  b.analytics.trackEvent("share_job");
  assert.equal(b.scripts.length, 1);
  assert.equal(b.consent.saveCookieChoice("denied"), false);
  b.analytics.trackEvent("share_job");
  assert.equal(b.consent.readCookieChoice(), "denied");
  assert.equal(b.window["ga-disable-G-3N6T2M5ED8"], true);
  unsubscribe();
});

test("a failed withdrawal write still overrides an older grant in this page", () => {
  const b = browser({
    blockedCookies: true,
    initialCookies: {
      zag_cookie_consent: `v1.granted.${Date.UTC(2026, 9, 24, 13)}`,
    },
  });
  const unsubscribe = b.consent.subscribeCookieChoice(() => {});
  assert.equal(b.consent.readCookieChoice(), "granted");
  assert.equal(b.consent.saveCookieChoice("denied"), false);
  b.window.dispatchEvent(new Event("focus"));
  assert.equal(b.consent.readCookieChoice(), "denied");
  b.analytics.trackEvent("apply_click");
  assert.equal(b.scripts.length, 0);
  unsubscribe();
});

test("cookie settings can reopen without changing the existing choice", () => {
  const b = browser();
  b.consent.saveCookieChoice("denied");
  let opened = 0;
  const unsubscribe = b.consent.subscribeCookieSettings(() => {
    opened++;
  });
  b.consent.openCookieSettings();
  assert.equal(opened, 1);
  assert.equal(b.consent.readCookieChoice(), "denied");
  unsubscribe();
  b.consent.openCookieSettings();
  assert.equal(opened, 1);
});

test("privacy settings that throw on cookie access cannot break rejection or site actions", () => {
  const b = browser({ throwCookieAccess: true, blockedStorage: true });
  assert.equal(b.consent.readCookieChoice(), null);
  assert.equal(b.consent.saveCookieChoice("denied"), false);
  assert.doesNotThrow(() => b.analytics.disableAnalytics());
  assert.doesNotThrow(() => b.analytics.trackEvent("apply_click"));
  assert.equal(b.window["ga-disable-G-3N6T2M5ED8"], true);
  assert.equal(b.scripts.length, 0);
});
