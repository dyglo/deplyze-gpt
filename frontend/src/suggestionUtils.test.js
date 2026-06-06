import { normalizeSuggestionText } from "./suggestionUtils";

test("collapses duplicate Locate all instances prefixes", () => {
  expect(normalizeSuggestionText("Locate all instances of all instances of banana and orange")).toBe(
    "Locate all instances of banana and orange"
  );
});

test("keeps Point suggestions clean", () => {
  expect(normalizeSuggestionText("Point to all instances of banana")).toBe("Point to banana");
  expect(normalizeSuggestionText("Point to banana")).toBe("Point to banana");
});

test("leaves unrelated Gemini suggestions unchanged", () => {
  expect(normalizeSuggestionText("Describe this image with Gemini")).toBe("Describe this image with Gemini");
});
