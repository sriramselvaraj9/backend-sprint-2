/**
 * frontend/__tests__/review-api.test.js
 *
 * Frontend Integration/Unit Tests: Review and Auth API interaction.
 * Verifies HTTP methods, request headers, authorization token injection,
 * response decoding, and structured error handling for 401, 403, 409, 422, and 500 errors.
 */

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { createReview, fetchFilms, loginUser } = require("../lib/review-utils.js");

describe("Frontend API Client Integration Suite", () => {
  const mockApiUrl = "http://test-api:8000";
  const mockFilmId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
  const validPayload = {
    film_id: mockFilmId,
    rating: 9,
    body: "Superb storytelling and brilliant performance by the lead cast.",
  };

  describe("createReview API Handling", () => {
    it("should successfully submit review and extract response data with trace headers", async () => {
      let capturedUrl = "";
      let capturedMethod = "";
      let capturedHeaders = {};
      let capturedBody = "";

      const mockFetch = async (url, options) => {
        capturedUrl = url;
        capturedMethod = options.method;
        capturedHeaders = options.headers;
        capturedBody = options.body;

        return {
          ok: true,
          status: 201,
          headers: new Headers({
            "Content-Type": "application/json",
            "X-Request-ID": "req-trace-uuid-1234",
            "X-Response-Time-Ms": "12.4",
          }),
          json: async () => ({
            id: "rev-uuid-5678",
            film_id: mockFilmId,
            rating: 9,
            body: validPayload.body,
            reviewer_display_name: "verified_critic",
            submitted_at: "2026-11-06T12:00:00Z",
          }),
        };
      };

      const result = await createReview(
        mockApiUrl,
        mockFilmId,
        validPayload,
        "valid.jwt.token",
        mockFetch
      );

      assert.equal(capturedUrl, `${mockApiUrl}/api/v1/films/${mockFilmId}/reviews`);
      assert.equal(capturedMethod, "POST");
      assert.equal(capturedHeaders["Authorization"], "Bearer valid.jwt.token");
      assert.equal(capturedHeaders["Content-Type"], "application/json");
      assert.equal(JSON.parse(capturedBody).rating, 9);

      assert.equal(result.id, "rev-uuid-5678");
      assert.equal(result.requestId, "req-trace-uuid-1234");
      assert.equal(result.responseTimeMs, "12.4");
    });

    it("should handle 401 Unauthorized with descriptive authentication error prefix", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 401,
        headers: new Headers({ "X-Request-ID": "req-trace-401" }),
        json: async () => ({ message: "Authorization header is required" }),
      });

      await assert.rejects(
        async () => {
          await createReview(mockApiUrl, mockFilmId, validPayload, "", mockFetch);
        },
        (err) => {
          assert.equal(err.status, 401);
          assert.ok(err.message.includes("Authentication Required:"));
          assert.ok(err.message.includes("Trace: req-trace-401"));
          return true;
        }
      );
    });

    it("should handle 403 Forbidden with role requirement error prefix", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 403,
        headers: new Headers({ "X-Request-ID": "req-trace-403" }),
        json: async () => ({ message: "Only verified critics or administrators may submit reviews" }),
      });

      await assert.rejects(
        async () => {
          await createReview(mockApiUrl, mockFilmId, validPayload, "viewer.token", mockFetch);
        },
        (err) => {
          assert.equal(err.status, 403);
          assert.ok(err.message.includes("Forbidden (Admin or Critic role required):"));
          return true;
        }
      );
    });

    it("should handle 409 Conflict with conflict error prefix (duplicate review)", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 409,
        headers: new Headers({ "X-Request-ID": "req-trace-409" }),
        json: async () => ({ message: "User has already submitted a review for this film" }),
      });

      await assert.rejects(
        async () => {
          await createReview(mockApiUrl, mockFilmId, validPayload, "critic.token", mockFetch);
        },
        (err) => {
          assert.equal(err.status, 409);
          assert.ok(err.message.includes("Conflict:"));
          return true;
        }
      );
    });

    it("should handle 422 Validation Error with detailed array extraction", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 422,
        headers: new Headers({ "X-Request-ID": "req-trace-422" }),
        json: async () => ({
          detail: [
            { loc: ["body", "rating"], msg: "Input should be greater than or equal to 1" },
            { loc: ["body", "body"], msg: "String should have at least 10 characters" },
          ],
        }),
      });

      await assert.rejects(
        async () => {
          await createReview(mockApiUrl, mockFilmId, validPayload, "critic.token", mockFetch);
        },
        (err) => {
          assert.equal(err.status, 422);
          assert.ok(err.message.includes("Validation Error:"));
          assert.ok(err.message.includes("Input should be greater than or equal to 1"));
          assert.ok(err.message.includes("String should have at least 10 characters"));
          return true;
        }
      );
    });

    it("should handle network failure gracefully", async () => {
      const mockFetch = async () => {
        throw new Error("Failed to fetch: Connection refused");
      };

      await assert.rejects(
        async () => {
          await createReview(mockApiUrl, mockFilmId, validPayload, "token", mockFetch);
        },
        /Failed to fetch: Connection refused/
      );
    });
  });

  describe("fetchFilms API Handling", () => {
    it("should parse film list from items property", async () => {
      const mockFetch = async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            { id: "1", title: "Film A", release_year: 2020, genre: "Sci-Fi", director: "Director A" },
            { id: "2", title: "Film B", release_year: 2022, genre: "Drama", director: "Director B" },
          ],
        }),
      });

      const films = await fetchFilms(mockApiUrl, "", mockFetch);
      assert.equal(films.length, 2);
      assert.equal(films[0].title, "Film A");
      assert.equal(films[1].title, "Film B");
    });

    it("should return empty list when receiving 401 or 403 without throwing unhandled error", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 401,
      });

      const films = await fetchFilms(mockApiUrl, "", mockFetch);
      assert.deepEqual(films, []);
    });

    it("should throw descriptive error on 500 server error", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 500,
      });

      await assert.rejects(async () => {
        await fetchFilms(mockApiUrl, "", mockFetch);
      }, /Failed to load films \(HTTP 500\)/);
    });
  });

  describe("loginUser API Handling", () => {
    it("should return token response on successful authentication", async () => {
      const mockFetch = async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: "jwt.access.token",
          refresh_token: "jwt.refresh.token",
          token_type: "bearer",
        }),
      });

      const data = await loginUser(mockApiUrl, "critic@example.com", "Password123!", mockFetch);
      assert.equal(data.access_token, "jwt.access.token");
      assert.equal(data.token_type, "bearer");
    });

    it("should throw error with message on authentication failure", async () => {
      const mockFetch = async () => ({
        ok: false,
        status: 401,
        json: async () => ({ message: "Invalid credentials" }),
      });

      await assert.rejects(async () => {
        await loginUser(mockApiUrl, "wrong@example.com", "BadPass", mockFetch);
      }, /Invalid credentials/);
    });
  });
});

