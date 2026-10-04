import Link from "next/link";

export default function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 group">
      <span
        className="w-8 h-8 rounded-md flex items-center justify-center text-sm font-bold transition-transform group-hover:scale-105"
        style={{
          background: "var(--primary)",
          color: "#ffffff",
        }}
      >
        Z
      </span>
      <span
        className="text-xl font-bold tracking-tight"
        style={{ color: "var(--text)" }}
      >
        ZAG<span style={{ color: "var(--primary)" }}>JobSearch</span>
      </span>
    </Link>
  );
}