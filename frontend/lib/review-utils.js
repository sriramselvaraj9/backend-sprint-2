/**
 * frontend/lib/review-utils.js
 *
 * Core domain utilities for Review validation, API communication,
 * and error envelope extraction used in the Film Review Platform frontend.
 */

/**
 * Validates review form fields according to platform business rules.
 *
 * @param {{ selectedFilmId: string, rating: number, body: string }} params
 * @returns {string[]} Array of human-readable validation error messages (empty if valid)
 */
function validateReviewForm({ selectedFilmId, rating, body }) {
  const errors = [];

  if (!selectedFilmId || typeof selectedFilmId !== "string" || selectedFilmId.trim() === "") {
    errors.push("Please select a film to review.");
  }

  if (typeof rating !== "number" || !Number.isInteger(rating) || rating < 1 || rating > 10) {
    errors.push("Rating must be an integer between 1 and 10.");
  }

  const trimmedBody = typeof body === "string" ? body.trim() : "";
  const charLen = trimmedBody.length;

  if (charLen < 10) {
    errors.push(`Review body must contain at least 10 characters (currently ${charLen}/10).`);
  } else if (charLen > 250) {
    errors.push(`Review body cannot exceed 250 characters (currently ${charLen}/250).`);
  }

  return errors;
}

/**
 * Submits a new film review via HTTP POST to the backend API.
 *
 * @param {string} apiUrl - Base API URL
 * @param {string} filmId - Target film UUID
 * @param {{ film_id: string, rating: number, body: string }} reviewData - Payload
 * @param {string} [token] - Optional JWT Bearer token
 * @param {typeof fetch} [fetchFn] - Injected fetch implementation for testing
 * @returns {Promise<object>} Parsed review response including trace headers
 */
async function createReview(apiUrl, filmId, reviewData, token = "", fetchFn = globalThis.fetch) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (token && token.trim()) {
    headers["Authorization"] = `Bearer ${token.trim()}`;
  }

  const endpoint = `${apiUrl.replace(/\/+$/, "")}/api/v1/films/${filmId}/reviews`;
  const res = await fetchFn(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(reviewData),
  });

  const reqId = res.headers?.get ? res.headers.get("X-Request-ID") : null;
  const resTime = res.headers?.get ? res.headers.get("X-Response-Time-Ms") : null;

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errorJson = await res.json();
      if (errorJson.message) {
        errorDetail = errorJson.message;
      } else if (errorJson.detail) {
        if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail
            .map((d) => (typeof d === "object" ? d.msg || JSON.stringify(d) : String(d)))
            .join("; ");
        } else {
          errorDetail = String(errorJson.detail);
        }
      }
    } catch {
      // Fallback
    }

    let prefix = "";
    if (res.status === 401) {
      prefix = "Authentication Required: ";
    } else if (res.status === 403) {
      prefix = "Forbidden (Admin or Critic role required): ";
    } else if (res.status === 409) {
      prefix = "Conflict: ";
    } else if (res.status === 422) {
      prefix = "Validation Error: ";
    }

    const error = new Error(`${prefix}${errorDetail}${reqId ? ` (Trace: ${reqId})` : ""}`);
    error.status = res.status;
    error.requestId = reqId;
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
 * Retrieves the catalog of films from the backend API.
 *
 * @param {string} apiUrl - Base API URL
 * @param {string} [token] - Optional JWT Bearer token
 * @param {typeof fetch} [fetchFn] - Injected fetch implementation
 * @returns {Promise<Array<object>>} List of film items
 */
async function fetchFilms(apiUrl, token = "", fetchFn = globalThis.fetch) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (token && token.trim()) {
    headers["Authorization"] = `Bearer ${token.trim()}`;
  }

  const endpoint = `${apiUrl.replace(/\/+$/, "")}/api/v1/films?page=1&page_size=50`;
  const res = await fetchFn(endpoint, {
    method: "GET",
    headers,
  });

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      return [];
    }
    throw new Error(`Failed to load films (HTTP ${res.status})`);
  }

  const data = await res.json();
  return data.items || data.films || (Array.isArray(data) ? data : []);
}

/**
 * Authenticates user credentials via POST /api/v1/auth/login.
 *
 * @param {string} apiUrl - Base API URL
 * @param {string} email - User email
 * @param {string} password - User password
 * @param {typeof fetch} [fetchFn] - Injected fetch implementation
 * @returns {Promise<{ access_token: string, refresh_token: string, token_type: string }>}
 */
async function loginUser(apiUrl, email, password, fetchFn = globalThis.fetch) {
  const endpoint = `${apiUrl.replace(/\/+$/, "")}/api/v1/auth/login`;
  const res = await fetchFn(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.message || `Login failed (HTTP ${res.status})`);
  }

  return await res.json();
}

module.exports = {
  validateReviewForm,
  createReview,
  fetchFilms,
  loginUser,
};

