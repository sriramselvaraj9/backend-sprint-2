import React from "react";

export default function HomePage() {
  const filmUiUrl = 
    process.env.NEXT_PUBLIC_FILM_UI_URL || "http://localhost:8000/ui/films";

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #0b0f19 0%, #060911 100%)",
        padding: "2rem 1.5rem 4rem",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div style={{ maxWidth: "1040px", width: "100%" }}>
        {/* Companion App Navigation / Header */}
        <header
          style={{
            marginBottom: "2rem",
            padding: "1.25rem 1.75rem",
            background: "rgba(17, 24, 39, 0.85)",
            backdropFilter: "blur(12px)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.75rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#818cf8",
                marginBottom: "0.35rem",
              }}
            >
              <span>⚛️ Next.js Companion Shell</span>
            </div>
            <h1
              style={{
                margin: 0,
                fontFamily: "'Outfit', sans-serif",
                fontSize: "1.5rem",
                fontWeight: 800,
                color: "#ffffff",
                letterSpacing: "-0.02em",
              }}
            >
              Film Review Platform
            </h1>
            <p
              style={{
                margin: "0.25rem 0 0",
                fontSize: "0.875rem",
                color: "#9ca3af",
              }}
            >
              Embedding the server-rendered FastAPI + Jinja2 + htmx view via an isolated iframe.
            </p>
          </div>

          <div
            style={{
              padding: "0.5rem 0.9rem",
              background: "rgba(0, 0, 0, 0.35)",
              border: "1px solid rgba(99, 102, 241, 0.3)",
              borderRadius: "10px",
              fontSize: "0.8rem",
              color: "#cbd5e1",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
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
              Target UI: <code style={{ color: "#a5b4fc" }}>{filmUiUrl}</code>
            </span>
          </div>
        </header>

        {/* Embedded Server-Rendered View */}
        <section
          style={{
            position: "relative",
            width: "100%",
            borderRadius: "20px",
            overflow: "hidden",
            boxShadow:
              "0 20px 40px -15px rgba(0, 0, 0, 0.7), 0 0 1px 1px rgba(255, 255, 255, 0.1)",
            background: "#0b0f19",
          }}
        >
          <iframe 
            src={filmUiUrl}
            title="Film Search Platform"
            style={{
              width: "100%",
              minHeight: "820px",
              border: "none",
              display: "block",
            }}
            loading="lazy"
          />
        </section>

        {/* Architecture Note Footer */}
        <footer
          style={{
            marginTop: "1.75rem",
            textAlign: "center",
            fontSize: "0.8rem",
            color: "#6b7280",
          }}
        >
          Day 1 Architecture: Next.js companion app embedding FastAPI server-rendered UI fragment.
        </footer>
      </div>
    </main>
  );
}
