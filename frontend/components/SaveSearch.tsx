"use client";
import Icon from "@/components/Icon";
import { useState } from "react";
import Link from "next/link";
import { accountRequest } from "@/lib/workspace";
import { trackEvent } from "@/lib/analytics";
export default function SaveSearch({ filters }: { filters: string }) {
  const [open, setOpen] = useState(false),
    [name, setName] = useState("My Ghana job search"),
    [email, setEmail] = useState(false),
    [ready, setReady] = useState(false),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="save-search">
      <button
        className="btn-outline"
        type="button"
        onClick={async () => {
          setOpen(!open);
          try {
            const [p, c] = await Promise.all([
              accountRequest("me"),
              fetch("/api/account/config").then((r) => r.json()),
            ]);
            setReady(Boolean(c.email_enabled && p.email_verified_at));
          } catch {
            setMessage("Log in to save this search.");
          }
        }}
      >
        Save this search
      </button>
      {open && (
        <div className="account-form">
          <label htmlFor="saved-search-name">Search name</label>
          <input
            id="saved-search-name"
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              disabled={!ready}
              checked={email}
              onChange={(e) => setEmail(e.target.checked)}
            />
            Email me a daily digest of new matches
          </label>
          {!ready && (
            <small>
              Email alerts need an available email service and a verified
              address in <Link href="/settings">Settings</Link>.
            </small>
          )}
          <button
            className="btn-primary"
            type="button"
            disabled={busy || !name.trim()}
            onClick={async () => {
              setBusy(true);
              try {
                await accountRequest("saved-searches", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    name,
                    filters: Object.fromEntries(new URLSearchParams(filters)),
                    email_alert: email,
                  }),
                });
                setMessage(
                  "Search saved. Open Saved searches to return to it.",
                );
                trackEvent("save_search", {
                  category:
                    new URLSearchParams(filters).get("category") || "jobs",
                });
              } catch (e) {
                setMessage((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Save search
          </button>
          <Link href="/saved-searches">View saved searches <Icon name="arrow-right" /></Link>
        </div>
      )}
      {message && (
        <p role="status">
          {message} <Link href="/login">Log in</Link>
        </p>
      )}
    </div>
  );
}
