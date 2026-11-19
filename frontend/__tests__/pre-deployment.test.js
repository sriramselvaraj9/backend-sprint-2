/**
 * frontend/__tests__/pre-deployment.test.js
 *
 * Frontend Unit Tests: Pre-deployment environment validation
 */

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { checkEnvVariables } = require("../scripts/pre-deployment.js");

describe("Pre-Deployment Safety Gate Script Tests", () => {
  describe("checkEnvVariables()", () => {
    it("should pass when all required client and server variables are set and valid", () => {
      const validEnv = {
        NEXT_PUBLIC_API_URL: "http://localhost:8000",
        NEXT_PUBLIC_FILM_UI_URL: "http://localhost:8000/ui/films",
        NODE_ENV: "production",
      };

      const result = checkEnvVariables(validEnv);
      assert.equal(result.valid, true);
      assert.equal(result.missing.length, 0);
    });

    it("should fail and collect NEXT_PUBLIC_API_URL when missing", () => {
      const env = {
        NEXT_PUBLIC_FILM_UI_URL: "http://localhost:8000/ui/films",
        NODE_ENV: "production",
      };

      const result = checkEnvVariables(env);
      assert.equal(result.valid, false);
      assert.ok(result.missing.includes("NEXT_PUBLIC_API_URL"));
    });

    it("should fail and collect NEXT_PUBLIC_FILM_UI_URL when missing", () => {
      const env = {
        NEXT_PUBLIC_API_URL: "http://localhost:8000",
        NODE_ENV: "production",
      };

      const result = checkEnvVariables(env);
      assert.equal(result.valid, false);
      assert.ok(result.missing.includes("NEXT_PUBLIC_FILM_UI_URL"));
    });

    it("should fail and collect server-only NODE_ENV when missing or empty", () => {
      const env = {
        NEXT_PUBLIC_API_URL: "http://localhost:8000",
        NEXT_PUBLIC_FILM_UI_URL: "http://localhost:8000/ui/films",
        NODE_ENV: "",
      };

      const result = checkEnvVariables(env);
      assert.equal(result.valid, false);
      assert.ok(result.missing.includes("NODE_ENV"));
    });

    it("should collect all missing variables together without stopping at the first", () => {
      const emptyEnv = {};
      const result = checkEnvVariables(emptyEnv);
      assert.equal(result.valid, false);
      assert.equal(result.missing.length, 3);
      assert.ok(result.missing.includes("NEXT_PUBLIC_API_URL"));
      assert.ok(result.missing.includes("NEXT_PUBLIC_FILM_UI_URL"));
      assert.ok(result.missing.includes("NODE_ENV"));
    });
  });
});
