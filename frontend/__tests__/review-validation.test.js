/**
 * frontend/__tests__/review-validation.test.js
 *
 * Frontend Unit Tests: Review form validation logic.
 * Covers positive cases, negative cases, boundary conditions, and whitespace trimming.
 */

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { validateReviewForm } = require("../lib/review-utils.js");

describe("Review Form Validation Suite", () => {
  const validFilmId = "11111111-1111-1111-1111-111111111111";

  describe("Positive Cases", () => {
    it("should accept valid review input with boundary rating 1", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 1,
        body: "A deeply flawed but ambitious piece of cinema.",
      });
      assert.equal(errors.length, 0);
    });

    it("should accept valid review input with mid-range rating 5", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 5,
        body: "Average production quality with decent acting performances throughout.",
      });
      assert.equal(errors.length, 0);
    });

    it("should accept valid review input with boundary rating 10", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 10,
        body: "An absolute masterpiece of modern filmmaking, truly breathtaking.",
      });
      assert.equal(errors.length, 0);
    });

    it("should accept review body at minimum boundary of exactly 10 characters", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8,
        body: "1234567890", // exactly 10 characters
      });
      assert.equal(errors.length, 0);
    });

    it("should accept review body at maximum boundary of exactly 250 characters", () => {
      const longBody = "A".repeat(250);
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8,
        body: longBody,
      });
      assert.equal(errors.length, 0);
    });
  });

  describe("Negative / Boundary Cases — Film Selection", () => {
    it("should reject empty film selection", () => {
      const errors = validateReviewForm({
        selectedFilmId: "",
        rating: 8,
        body: "Great movie with wonderful storytelling.",
      });
      assert.ok(errors.some((e) => e.includes("select a film")));
    });

    it("should reject whitespace-only film selection", () => {
      const errors = validateReviewForm({
        selectedFilmId: "   ",
        rating: 8,
        body: "Great movie with wonderful storytelling.",
      });
      assert.ok(errors.some((e) => e.includes("select a film")));
    });

    it("should reject null or undefined film selection", () => {
      const errors = validateReviewForm({
        selectedFilmId: null,
        rating: 8,
        body: "Great movie with wonderful storytelling.",
      });
      assert.ok(errors.some((e) => e.includes("select a film")));
    });
  });

  describe("Negative / Boundary Cases — Rating Constraints", () => {
    it("should reject rating 0 below lower bound", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 0,
        body: "Valid review body here.",
      });
      assert.ok(errors.some((e) => e.includes("Rating must be an integer between 1 and 10")));
    });

    it("should reject negative ratings", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: -5,
        body: "Valid review body here.",
      });
      assert.ok(errors.some((e) => e.includes("Rating must be an integer between 1 and 10")));
    });

    it("should reject rating 11 above upper bound", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 11,
        body: "Valid review body here.",
      });
      assert.ok(errors.some((e) => e.includes("Rating must be an integer between 1 and 10")));
    });

    it("should reject non-integer / floating-point ratings", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8.5,
        body: "Valid review body here.",
      });
      assert.ok(errors.some((e) => e.includes("Rating must be an integer between 1 and 10")));
    });
  });

  describe("Negative / Boundary Cases — Review Body Constraints", () => {
    it("should reject body with fewer than 10 characters (9 characters)", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8,
        body: "123456789", // 9 chars
      });
      assert.ok(errors.some((e) => e.includes("at least 10 characters (currently 9/10)")));
    });

    it("should reject body with whitespace padding that trims below 10 characters", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8,
        body: "   short   ", // 5 non-whitespace chars
      });
      assert.ok(errors.some((e) => e.includes("at least 10 characters (currently 5/10)")));
    });

    it("should reject empty body string", () => {
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8,
        body: "",
      });
      assert.ok(errors.some((e) => e.includes("at least 10 characters")));
    });

    it("should reject body exceeding 250 characters (251 characters)", () => {
      const tooLongBody = "B".repeat(251);
      const errors = validateReviewForm({
        selectedFilmId: validFilmId,
        rating: 8,
        body: tooLongBody,
      });
      assert.ok(errors.some((e) => e.includes("cannot exceed 250 characters (currently 251/250)")));
    });
  });

  describe("Compound Validation", () => {
    it("should report multiple errors simultaneously when multiple fields are invalid", () => {
      const errors = validateReviewForm({
        selectedFilmId: "",
        rating: 99,
        body: "tiny",
      });
      assert.equal(errors.length, 3);
      assert.ok(errors.some((e) => e.includes("select a film")));
      assert.ok(errors.some((e) => e.includes("Rating must be an integer")));
      assert.ok(errors.some((e) => e.includes("at least 10 characters")));
    });
  });
});

