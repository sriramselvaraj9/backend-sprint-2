import React from "react";
import Link from "next/link";

export default function HomePage() {
  const filmUiUrl =
    process.env.NEXT_PUBLIC_FILM_UI_URL || "http://localhost:8000/ui/films";

  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        backgroundColor: "#060911",
      }}
    >
      {/* Top Application Bar - Spanning Entire Width */}
      <header
        style={{
          height: "68px",
          width: "100%",
          padding: "0 2rem",
          background: "rgba(11, 15, 25, 0.95)",
          backdropFilter: "blur(16px)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexShrink: 0,
          zIndex: 20,
        }}
      >
        {/* Brand & Subtitle */}
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.25rem",
              boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
            }}
          >
            🎬
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <h1
                style={{
                  margin: 0,
                  fontFamily: "'Roboto', sans-serif",
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  color: "#ffffff",
                  letterSpacing: "-0.01em",
                }}
              >
                Film Review Platform
              </h1>
            </div>
            <p
              style={{
                margin: "0.15rem 0 0",
                fontSize: "0.8rem",
                color: "#94a3b8",
              }}
            >
              Search, discover and review films
            </p>
          </div>
        </div>

        {/* Action Controls & Navigation */}
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div
            style={{
              display: "none",
              padding: "0.4rem 0.85rem",
              background: "rgba(0, 0, 0, 0.4)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "8px",
              fontSize: "0.78rem",
              color: "#cbd5e1",
              alignItems: "center",
              gap: "0.5rem",
            }}
            className="header-target-badge"
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: "#10b981",
                boxShadow: "0 0 8px #10b981",
              }}
            />
            <span>
              Target: <code style={{ color: "#a5b4fc" }}>{filmUiUrl}</code>
            </span>
          </div>

          <Link
            href="/reviews"
            id="nav-add-review"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.55rem 1.25rem",
              background: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
              border: "none",
              borderRadius: "10px",
              fontSize: "0.85rem",
              fontWeight: 700,
              color: "#ffffff",
              textDecoration: "none",
              boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
              transition: "transform 0.15s ease, box-shadow 0.15s ease",
            }}
          >
            <span>⭐ Add Review</span>
            <span style={{ fontSize: "1rem" }}>&rarr;</span>
          </Link>
        </div>
      </header>

      {/* Embedded Full-Bleed View Area - Zero Double Scrollbars */}
      <main
        style={{
          flex: 1,
          width: "100%",
          position: "relative",
          overflow: "hidden",
          backgroundColor: "#060911",
        }}
      >
        <iframe
          src={filmUiUrl}
          title="Film Search Platform"
          style={{
            width: "100%",
            height: "100%",
            border: "none",
            display: "block",
          }}
          loading="lazy"
        />
      </main>
    </div>
  );
}

