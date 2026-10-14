"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

interface FilmItem {
  id: string;
  title: string;
  release_year: number;
  genre: string;
  director: string;
  average_rating?: number | null;
  review_count?: number;
}

interface ReviewCreateInput {
  film_id: string;
  rating: number;
  body: string;
}

interface ReviewResponseData {
  id: string;
  film_id: string;
  rating: number;
  body: string;
  reviewer_display_name: string;
  submitted_at: string;
  requestId?: string | null;
  responseTimeMs?: string | null;
}

interface BackendErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
}

export default function ReviewSubmissionPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"; 

  // Form State
  const [films, setFilms] = useState<FilmItem[]>([]);
  const [selectedFilmId, setSelectedFilmId] = useState<string>("");
  const [rating, setRating] = useState<number>(10);
  const [body, setBody] = useState<string>("");

  // Authentication State
  const [authToken, setAuthToken] = useState<string>("");
  const [refreshToken, setRefreshToken] = useState<string>("");
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [loginEmail, setLoginEmail] = useState<string>("");
  const [loginPassword, setLoginPassword] = useState<string>("");
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);
  const [isLoggingOut, setIsLoggingOut] = useState<boolean>(false);

  // UI Status State
  const [isLoadingFilms, setIsLoadingFilms] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [successResult, setSuccessResult] = useState<ReviewResponseData | null>(null);

  /**
   * Fetches user profile using the authenticated session.
   */
  async function fetchUserProfile(token: string): Promise<UserProfile | null> {
    try {
      const res = await fetch(`${apiUrl}/api/v1/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Ignore network errors on profile fetch
    }
    return null;
  }

  // Load saved token from localStorage on mount and retrieve user profile
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem("film_platform_token");
      const savedRefreshToken = localStorage.getItem("film_platform_refresh_token");
      if (savedRefreshToken) {
        setRefreshToken(savedRefreshToken);
      }
      if (savedToken) {
        setAuthToken(savedToken);
        fetchUserProfile(savedToken).then((profile) => {
          if (profile) {
            setCurrentUser(profile);
          } else {
            handleLogout(false);
          }
        });
      }
    } catch {
      // Ignore localStorage access issues in sandbox
    }
  }, []);

  // Fetch films whenever authToken changes or on mount
  useEffect(() => {
    fetchFilms();
  }, [authToken]);

  /**
   * Retrieves available active films from the backend API.
   */
  async function fetchFilms(): Promise<void> {
    setIsLoadingFilms(true);
    setErrorMessage(null);
    try {
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      if (authToken.trim()) {
        headers["Authorization"] = `Bearer ${authToken.trim()}`;
      }

      const res = await fetch(`${apiUrl}/api/v1/films?page=1&page_size=50`, {
        method: "GET",
        headers,
      });

      if (!res.ok) {
        // If unauthenticated, fallback to public search fragment or notify user
        if (res.status === 401 || res.status === 403) {
          // Keep films empty and prompt user to login
          setFilms([]);
          return;
        }
        throw new Error(`Failed to load films (HTTP ${res.status})`);
      }

      const data = await res.json();
      const filmList: FilmItem[] = data.items || data.films || (Array.isArray(data) ? data : []);
      setFilms(filmList);

      if (filmList.length > 0 && !selectedFilmId) {
        setSelectedFilmId(filmList[0].id);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Network error loading films";
      setErrorMessage(message);
    } finally {
      setIsLoadingFilms(false);
    }
  }

  /**
   * Logs in using email and password via POST /api/v1/auth/login and stores session.
   */
  async function handleLogin(e?: React.FormEvent): Promise<void> {
    if (e) e.preventDefault();
    setIsLoggingIn(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `Login failed (HTTP ${res.status})`);
      }

      const data = await res.json();
      const token = data.access_token;
      const refToken = data.refresh_token || "";
      setAuthToken(token);
      setRefreshToken(refToken);
      try {
        localStorage.setItem("film_platform_token", token);
        if (refToken) {
          localStorage.setItem("film_platform_refresh_token", refToken);
        }
      } catch {
        // Ignore
      }

      const profile = await fetchUserProfile(token);
      setCurrentUser(profile);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to log in";
      setErrorMessage(`Login Error: ${msg}`);
    } finally {
      setIsLoggingIn(false);
    }
  }

  /**
   * Logs out the user and cleans up active session.
   * Calls the backend logout endpoint (POST /api/v1/auth/logout) to delete refresh token from Redis.
   */
  async function handleLogout(callApi: boolean = true): Promise<void> {
    setIsLoggingOut(true);
    const token = authToken || (typeof window !== "undefined" ? localStorage.getItem("film_platform_token") : null);
    const storedRefreshToken = refreshToken || (typeof window !== "undefined" ? localStorage.getItem("film_platform_refresh_token") : null);

    if (callApi && token) {
      try {
        const res = await fetch(`${apiUrl}/api/v1/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: storedRefreshToken ? JSON.stringify({ refresh_token: storedRefreshToken }) : JSON.stringify({}),
        });

        if (!res.ok) {
          console.warn(`Logout request responded with status: ${res.status}`);
        }
      } catch (err) {
        console.error("Logout request failed:", err);
      }
    }

    setAuthToken("");
    setRefreshToken("");
    setCurrentUser(null);
    try {
      localStorage.removeItem("film_platform_token");
      localStorage.removeItem("film_platform_refresh_token");
    } catch {
      // Ignore
    } finally {
      setIsLoggingOut(false);
    }
  }

  /**
   * Validates form fields on the client side according to backend validation rules.
   */
  function validateReviewForm(): string[] {
    const errors: string[] = [];
    if (!selectedFilmId || selectedFilmId.trim() === "") {
      errors.push("Please select a film to review.");
    }

    if (!Number.isInteger(rating) || rating < 1 || rating > 10) {
      errors.push("Rating must be an integer between 1 and 10.");
    }

    const charLen = body.trim().length;
    if (charLen < 10) {
      errors.push(
        `Review body must contain at least 10 characters (currently ${charLen}/10).`
      );
    } else if (charLen > 250) {
      errors.push(
        `Review body cannot exceed 250 characters (currently ${charLen}/250).`
      );
    }

    return errors;
  }

  /**
   * Calls the review API to persist the new review record.
   */
  async function createReview(
    filmId: string,
    reviewData: ReviewCreateInput,
    token: string
  ): Promise<ReviewResponseData> {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Submit to POST /films/{film_id}/reviews as specified in requirements
    const res = await fetch(`${apiUrl}/api/v1/films/${filmId}/reviews`, {
      method: "POST",
      headers,
      body: JSON.stringify(reviewData),
    });

    const reqId = res.headers.get("X-Request-ID");
    const resTime = res.headers.get("X-Response-Time-Ms");

    if (!res.ok) {
      let errorDetail = `Request failed with status ${res.status}`;
      try {
        const errorJson = await res.json();
        if (errorJson.message) {
          errorDetail = errorJson.message;
        } else if (errorJson.detail) {
          if (Array.isArray(errorJson.detail)) {
            errorDetail = errorJson.detail
              .map((d: BackendErrorDetail) => d.msg || JSON.stringify(d))
              .join("; ");
          } else {
            errorDetail = String(errorJson.detail);
          }
        }
      } catch {
        // Fallback to status text
      }

      const error = new Error(errorDetail);
      (error as unknown as { status: number; requestId: string | null }).status = res.status;
      (error as unknown as { status: number; requestId: string | null }).requestId = reqId;
      throw error;
    }

    const responseData = await res.json();
    return {
      ...responseData,
      requestId: reqId,
      responseTimeMs: resTime,
    };
  }

  /**
   * Handles review form submission, validation, loading state, and error handling.
   */
  async function handleReviewSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();

    // Prevent duplicate submissions
    if (isSubmitting) {
      return;
    }

    setErrorMessage(null);
    setValidationErrors([]);
    setSuccessResult(null);

    // Client-side validation
    const errors = validateReviewForm();
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }

    setIsSubmitting(true);

    try {
      const reviewPayload: ReviewCreateInput = {
        film_id: selectedFilmId,
        rating: Math.round(rating),
        body: body.trim(),
      };

      const result = await createReview(selectedFilmId, reviewPayload, authToken.trim());

      setSuccessResult(result);
      setBody("");
      // Refresh films catalog in background
      fetchFilms();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      const status = (err as { status?: number })?.status;
      const reqId = (err as { requestId?: string | null })?.requestId;

      let prefix = "";
      if (status === 401) {
        prefix = "Authentication Required: ";
      } else if (status === 403) {
        prefix = "Forbidden (Admin or Critic role required): ";
      } else if (status === 409) {
        prefix = "Conflict: ";
      } else if (status === 422) {
        prefix = "Validation Error: ";
      }

      setErrorMessage(`${prefix}${msg}${reqId ? ` (Trace: ${reqId})` : ""}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  const selectedFilm = films.find((f) => f.id === selectedFilmId);
  const charCount = body.trim().length;
  const isBodyValid = charCount >= 10 && charCount <= 250;

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #0b0f19 0%, #060911 100%)",
        padding: "1.5rem 2rem 3rem",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div style={{ maxWidth: "1440px", width: "100%" }}>
        {/* Navigation & Header */}
        <header
          style={{
            marginBottom: "1.75rem",
            padding: "1rem 1.75rem",
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
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div
              style={{
                width: "42px",
                height: "42px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.3rem",
                boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
              }}
            >
              ⭐
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <h1
                  style={{
                    margin: 0,
                    fontFamily: "'Roboto', sans-serif",
                    fontSize: "1.45rem",
                    fontWeight: 700,
                    color: "#ffffff",
                    letterSpacing: "-0.01em",
                  }}
                >
                  Submit Film Review
                </h1>
              </div>
              <p style={{ margin: "0.2rem 0 0", fontSize: "0.82rem", color: "#9ca3af" }}>
                Publish verified film critiques
              </p>
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <Link
              href="/"
              id="back-to-catalog-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.55rem 1.25rem",
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: "10px",
                fontSize: "0.85rem",
                fontWeight: 600,
                color: "#cbd5e1",
                textDecoration: "none",
                transition: "all 0.2s ease",
              }}
            >
              &larr; Catalog Browser
            </Link>
          </div>
        </header>

        {/* Spacious 2-Column Responsive Dashboard Layout */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
            gap: "1.75rem",
            alignItems: "start",
          }}
        >
          {/* LEFT COLUMN: Film Selection & Film Overview Card */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Film Selector Card */}
            <section
              style={{
                padding: "1.5rem",
                background: "rgba(17, 24, 39, 0.85)",
                backdropFilter: "blur(12px)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "18px",
                boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.5)",
              }}
            >
              <div style={{ marginBottom: "0.75rem" }}>
                <label
                  htmlFor="film-selector"
                  style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f1f5f9" }}
                >
                  Target Film <span style={{ color: "#ef4444" }}>*</span>
                </label>
              </div>

              <select
                id="film-selector"
                value={selectedFilmId}
                onChange={(e) => setSelectedFilmId(e.target.value)}
                disabled={isLoadingFilms || isSubmitting}
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "0.85rem 1rem",
                  background: "rgba(15, 23, 42, 0.95)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                  borderRadius: "12px",
                  color: "#ffffff",
                  fontSize: "0.95rem",
                  fontFamily: "inherit",
                  cursor: "pointer",
                  marginBottom: "1rem",
                }}
              >
                {films.length === 0 ? (
                  <option value="">
                    {isLoadingFilms ? "Loading films..." : "No films available (Check connection)"}
                  </option>
                ) : (
                  films.map((film) => (
                    <option key={film.id} value={film.id} style={{ background: "#0f172a" }}>
                      {film.title} ({film.release_year}) &bull; {film.genre} &bull; Directed by {film.director}
                      {film.average_rating ? ` [Avg: ${film.average_rating}★]` : " [Unrated]"}
                    </option>
                  ))
                )}
              </select>

              {/* Selected Film Preview Showcase */}
              {selectedFilm ? (
                <div
                  style={{
                    padding: "1.25rem",
                    background: "rgba(15, 23, 42, 0.7)",
                    borderRadius: "12px",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.75rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.5rem" }}>
                    <div>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          padding: "0.2rem 0.6rem",
                          borderRadius: "6px",
                          background: "rgba(99, 102, 241, 0.2)",
                          color: "#a5b4fc",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        {selectedFilm.genre}
                      </span>
                      <h3
                        style={{
                          margin: "0.5rem 0 0.15rem",
                          fontSize: "1.15rem",
                          fontWeight: 800,
                          color: "#ffffff",
                        }}
                      >
                        {selectedFilm.title}
                      </h3>
                      <p style={{ margin: 0, fontSize: "0.8rem", color: "#94a3b8" }}>
                        {selectedFilm.release_year} &bull; Directed by <strong style={{ color: "#cbd5e1" }}>{selectedFilm.director}</strong>
                      </p>
                    </div>
                  </div>

                  {/* Aggregate Badge Row */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "1rem",
                      paddingTop: "0.5rem",
                      borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                      <span style={{ fontSize: "1rem", color: "#fbbf24" }}>★</span>
                      <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc" }}>
                        {selectedFilm.average_rating !== null && selectedFilm.average_rating !== undefined
                          ? Number(selectedFilm.average_rating).toFixed(1)
                          : "No ratings yet"}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                      {selectedFilm.review_count || 0} verified reviews
                    </div>
                  </div>
                </div>
              ) : null}
            </section>
          </div>

          {/* RIGHT COLUMN: Authentication & Review Editor */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Authentication Card */}
            <section
              style={{
                padding: "1.25rem 1.5rem",
                background: "rgba(15, 23, 42, 0.75)",
                border: "1px solid rgba(99, 102, 241, 0.25)",
                borderRadius: "18px",
              }}
            >
              {currentUser || authToken ? (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "1rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
                    <div
                      style={{
                        width: "44px",
                        height: "44px",
                        borderRadius: "50%",
                        background: "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        color: "#ffffff",
                        boxShadow: "0 2px 10px rgba(99, 102, 241, 0.4)",
                      }}
                    >
                      {currentUser?.username ? currentUser.username[0].toUpperCase() : "B"}
                    </div>
                    <div>
                      <div>
                        <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>
                          {currentUser?.username || "bob_critic"}
                        </span>
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                        {currentUser?.email || "bob@example.com"}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    id="logout-btn"
                    onClick={() => handleLogout(true)}
                    disabled={isLoggingOut}
                    style={{
                      background: "rgba(239, 68, 68, 0.15)",
                      color: isLoggingOut ? "#fca5a5" : "#f87171",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      borderRadius: "8px",
                      padding: "0.5rem 1rem",
                      fontSize: "0.82rem",
                      fontWeight: 600,
                      cursor: isLoggingOut ? "not-allowed" : "pointer",
                      transition: "all 0.15s ease",
                      opacity: isLoggingOut ? 0.7 : 1,
                    }}
                  >
                    {isLoggingOut ? "Signing Out..." : "Sign Out"}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "#e2e8f0" }}>
                      Sign In as Critic
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                      Only authorized Critics and Admins can publish reviews
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" }}>
                    <div>
                      <label htmlFor="login-email" style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", marginBottom: "0.25rem" }}>
                        Email Address
                      </label>
                      <input
                        type="email"
                        id="login-email"
                        value={loginEmail}
                        onChange={(e) => setLoginEmail(e.target.value)}
                        placeholder="name@example.com"
                        required
                        style={{
                          width: "100%",
                          boxSizing: "border-box",
                          padding: "0.6rem 0.8rem",
                          background: "rgba(0, 0, 0, 0.4)",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "8px",
                          color: "#ffffff",
                          fontSize: "0.85rem",
                        }}
                      />
                    </div>

                    <div>
                      <label htmlFor="login-password" style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", marginBottom: "0.25rem" }}>
                        Password
                      </label>
                      <input
                        type="password"
                        id="login-password"
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        placeholder="Enter password"
                        required
                        style={{
                          width: "100%",
                          boxSizing: "border-box",
                          padding: "0.6rem 0.8rem",
                          background: "rgba(0, 0, 0, 0.4)",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "8px",
                          color: "#ffffff",
                          fontSize: "0.85rem",
                        }}
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.25rem" }}>
                    <button
                      type="submit"
                      id="login-submit-btn"
                      disabled={isLoggingIn}
                      style={{
                        background: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "8px",
                        padding: "0.55rem 1.25rem",
                        fontSize: "0.85rem",
                        fontWeight: 700,
                        cursor: isLoggingIn ? "not-allowed" : "pointer",
                        boxShadow: "0 2px 8px rgba(99, 102, 241, 0.3)",
                        opacity: isLoggingIn ? 0.7 : 1,
                      }}
                    >
                      {isLoggingIn ? "Signing In..." : "Sign In & Authorize"}
                    </button>
                  </div>
                </form>
              )}
            </section>

            {/* Success Alert Banner */}
            {successResult && (
              <section
                id="review-success-banner"
                style={{
                  padding: "1.25rem 1.5rem",
                  background: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(16, 185, 129, 0.4)",
                  borderRadius: "16px",
                  boxShadow: "0 8px 24px -6px rgba(16, 185, 129, 0.2)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <span style={{ fontSize: "1.2rem" }}>🎉</span>
                  <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "#34d399" }}>
                    Review Submitted Successfully!
                  </h3>
                </div>
                <p style={{ margin: "0 0 0.75rem", fontSize: "0.85rem", color: "#cbd5e1" }}>
                  The review committed and scheduled asynchronous aggregate recalculation in the background.
                </p>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                    gap: "0.75rem",
                    fontSize: "0.78rem",
                    background: "rgba(0, 0, 0, 0.3)",
                    padding: "0.75rem 1rem",
                    borderRadius: "10px",
                  }}
                >
                  <div>
                    <span style={{ color: "#9ca3af" }}>Review ID:</span>
                    <p style={{ margin: "0.15rem 0 0", fontFamily: "monospace", color: "#e2e8f0" }}>
                      {successResult.id}
                    </p>
                  </div>
                  <div>
                    <span style={{ color: "#9ca3af" }}>Reviewer:</span>
                    <p style={{ margin: "0.15rem 0 0", fontWeight: 600, color: "#e2e8f0" }}>
                      {successResult.reviewer_display_name}
                    </p>
                  </div>
                  <div>
                    <span style={{ color: "#9ca3af" }}>Rating:</span>
                    <p style={{ margin: "0.15rem 0 0", fontWeight: 700, color: "#fbbf24" }}>
                      ★ {successResult.rating} / 10
                    </p>
                  </div>
                  {successResult.requestId && (
                    <div>
                      <span style={{ color: "#9ca3af" }}>X-Request-ID:</span>
                      <p style={{ margin: "0.15rem 0 0", fontFamily: "monospace", color: "#818cf8" }}>
                        {successResult.requestId}
                      </p>
                    </div>
                  )}
                  {successResult.responseTimeMs && (
                    <div>
                      <span style={{ color: "#9ca3af" }}>X-Response-Time-Ms:</span>
                      <p style={{ margin: "0.15rem 0 0", fontWeight: 600, color: "#34d399" }}>
                        {successResult.responseTimeMs} ms
                      </p>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Error Banners */}
            {errorMessage && (
              <section
                id="review-error-banner"
                style={{
                  padding: "1rem 1.25rem",
                  background: "rgba(239, 68, 68, 0.12)",
                  border: "1px solid rgba(239, 68, 68, 0.4)",
                  borderRadius: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "1.1rem" }}>⚠️</span>
                  <p style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600, color: "#f87171" }}>
                    {errorMessage}
                  </p>
                </div>
              </section>
            )}

            {validationErrors.length > 0 && (
              <section
                id="client-validation-banner"
                style={{
                  padding: "1rem 1.25rem",
                  background: "rgba(245, 158, 11, 0.12)",
                  border: "1px solid rgba(245, 158, 11, 0.4)",
                  borderRadius: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                  <span style={{ fontSize: "1.1rem" }}>ℹ️</span>
                  <p style={{ margin: 0, fontSize: "0.85rem", fontWeight: 700, color: "#fbbf24" }}>
                    Please correct the following errors:
                  </p>
                </div>
                <ul style={{ margin: "0.25rem 0 0 1.25rem", padding: 0, fontSize: "0.8rem", color: "#fde68a" }}>
                  {validationErrors.map((err, idx) => (
                    <li key={idx} style={{ marginBottom: "0.2rem" }}>{err}</li>
                  ))}
                </ul>
              </section>
            )}

            {/* Main Review Form Card */}
            <section
              style={{
                background: "rgba(17, 24, 39, 0.85)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "18px",
                padding: "2rem",
                boxShadow: "0 20px 40px -15px rgba(0, 0, 0, 0.7)",
              }}
            >
              <form onSubmit={handleReviewSubmit} noValidate>
                {/* Rating Input */}
                <div style={{ marginBottom: "1.75rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                    <label
                      htmlFor="rating-input"
                      style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f1f5f9" }}
                    >
                      Critic Rating (1 to 10) <span style={{ color: "#ef4444" }}>*</span>
                    </label>
                    <span
                      id="rating-display"
                      style={{
                        fontSize: "1.05rem",
                        fontWeight: 800,
                        color: "#fbbf24",
                      }}
                    >
                      ★ {rating} / 10
                    </span>
                  </div>

                  {/* Rating Buttons */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(10, 1fr)",
                      gap: "0.4rem",
                      marginBottom: "0.75rem",
                    }}
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((starVal) => {
                      const isSelected = rating === starVal;
                      return (
                        <button
                          key={starVal}
                          type="button"
                          id={`rating-star-${starVal}`}
                          onClick={() => setRating(starVal)}
                          disabled={isSubmitting}
                          style={{
                            padding: "0.55rem 0",
                            background: isSelected
                              ? "linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)"
                              : starVal <= rating
                              ? "rgba(251, 191, 36, 0.15)"
                              : "rgba(255, 255, 255, 0.05)",
                            border: isSelected
                              ? "1px solid #fbbf24"
                              : "1px solid rgba(255, 255, 255, 0.08)",
                            borderRadius: "8px",
                            color: isSelected ? "#000000" : starVal <= rating ? "#fbbf24" : "#94a3b8",
                            fontWeight: isSelected ? 800 : 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                          }}
                        >
                          {starVal}
                        </button>
                      );
                    })}
                  </div>

                  <input
                    type="range"
                    id="rating-input"
                    min={1}
                    max={10}
                    step={1}
                    value={rating}
                    onChange={(e) => setRating(parseInt(e.target.value, 10))}
                    disabled={isSubmitting}
                    style={{
                      width: "100%",
                      accentColor: "#fbbf24",
                      cursor: "pointer",
                    }}
                  />
                </div>

                {/* Review Body Textarea */}
                <div style={{ marginBottom: "2rem" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "0.5rem",
                    }}
                  >
                    <label
                      htmlFor="review-body-input"
                      style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f1f5f9" }}
                    >
                      Review Body <span style={{ color: "#ef4444" }}>*</span>
                    </label>
                    <span
                      id="body-char-counter"
                      style={{
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        color: isBodyValid ? "#34d399" : charCount > 250 ? "#ef4444" : "#f59e0b",
                      }}
                    >
                      {charCount} / 250 chars{" "}
                      {charCount < 10
                        ? "(min 10 char)"
                        : charCount > 250
                        ? `(${charCount - 250} over limit)`
                        : "✓"}
                    </span>
                  </div>

                  <textarea
                    id="review-body-input"
                    rows={6}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    maxLength={250}
                    placeholder="Write your review here... (Minimum 10 char, maximum 250 char)"
                    disabled={isSubmitting}
                    style={{
                      width: "100%",
                      boxSizing: "border-box",
                      padding: "0.9rem 1rem",
                      background: "rgba(15, 23, 42, 0.95)",
                      border: `1px solid ${
                        charCount === 0
                          ? "rgba(255, 255, 255, 0.15)"
                          : isBodyValid
                          ? "rgba(16, 185, 129, 0.5)"
                          : "rgba(245, 158, 11, 0.5)"
                      }`,
                      borderRadius: "12px",
                      color: "#ffffff",
                      fontSize: "0.95rem",
                      fontFamily: "'Roboto', sans-serif",
                      resize: "vertical",
                      lineHeight: 1.6,
                    }}
                  />

                  {/* Character Count Progress Bar */}
                  <div
                    style={{
                      height: "4px",
                      width: "100%",
                      background: "rgba(255, 255, 255, 0.08)",
                      borderRadius: "2px",
                      marginTop: "0.5rem",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(100, (charCount / 250) * 100)}%`,
                        background: isBodyValid ? "#10b981" : charCount > 250 ? "#ef4444" : "#f59e0b",
                        transition: "width 0.2s ease, background-color 0.2s ease",
                      }}
                    />
                  </div>
                </div>

                {/* Submit Action */}
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    type="submit"
                    id="submit-review-btn"
                    disabled={isSubmitting || !selectedFilmId}
                    style={{
                      padding: "0.9rem 2.25rem",
                      background: isSubmitting
                        ? "rgba(99, 102, 241, 0.5)"
                        : "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
                      border: "none",
                      borderRadius: "12px",
                      color: "#ffffff",
                      fontSize: "1rem",
                      fontWeight: 700,
                      cursor: isSubmitting || !selectedFilmId ? "not-allowed" : "pointer",
                      boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
                      transition: "all 0.2s ease",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      fontFamily: "'Roboto', sans-serif",
                    }}
                  >
                    {isSubmitting ? (
                      <>
                        <span
                          style={{
                            display: "inline-block",
                            width: "14px",
                            height: "14px",
                            border: "2px solid rgba(255, 255, 255, 0.3)",
                            borderTopColor: "#ffffff",
                            borderRadius: "50%",
                            animation: "spin 0.8s linear infinite",
                          }}
                        />
                        <span>Submitting Review...</span>
                      </>
                    ) : (
                      <span>Publish Critic Review</span>
                    )}
                  </button>
                </div>
              </form>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}


