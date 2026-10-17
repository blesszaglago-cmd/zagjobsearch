import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
export const alt =
  "jobs.ac.ghana. Jobs, internships, scholarships and your application tracker.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export default async function Image() {
  const mark = await readFile(
    join(process.cwd(), "public/brand/jobs-ac-ghana-mark.png"),
  );
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#063f2b",
        padding: "58px 76px",
        color: "#fff",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          marginBottom: 40,
          gap: 22,
        }}
      >
        <div
          style={{
            display: "flex",
            background: "#fff",
            borderRadius: 16,
            padding: 9,
          }}
        >
          <img
            src={`data:image/png;base64,${mark.toString("base64")}`}
            alt=""
            width={100}
            height={100}
          />
        </div>
        <span style={{ fontSize: 52, fontWeight: 700 }}>
          jobs.ac.<span style={{ color: "#f6d94a" }}>ghana</span>
        </span>
      </div>
      <div style={{ display: "flex", fontSize: 74, fontWeight: 700 }}>
        Your next opportunity.
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 74,
          fontWeight: 700,
          color: "#f6d94a",
        }}
      >
        Rooted in Ghana.
      </div>
      <div style={{ display: "flex", fontSize: 27, marginTop: 34 }}>
        Jobs · Internships · Scholarships · Application tracking
      </div>
      <div
        style={{
          display: "flex",
          height: 7,
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
        }}
      >
        <div style={{ display: "flex", flex: 1, background: "#ce1126" }} />
        <div style={{ display: "flex", flex: 1, background: "#fcd116" }} />
        <div style={{ display: "flex", flex: 1, background: "#006b3f" }} />
      </div>
    </div>,
    size,
  );
}
