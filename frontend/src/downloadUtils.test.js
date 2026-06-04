import { apiDownloadUrl, isApiUrl, jobIdFromOutputSource, outputPathDownloadUrl } from "./downloadUtils";

const API = "https://vision-sys.web.app/api";
const R2_OUTPUT_URL = "https://34c5468ebfcd71e2a958b25cfb0bde40.r2.cloudflarestorage.com/deplyzegpt-storage/outputs/RDM7Z408tERD8GBw2jDizML7mZt2/c998ae90-d27a-4da9-802a-f14f734c2d2a/6249f72c-4c2f-4b81-8eb0-6662719122d7/output.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256";

test("converts R2 output URLs into authenticated API download URLs", () => {
  expect(outputPathDownloadUrl(R2_OUTPUT_URL, API)).toBe(
    "https://vision-sys.web.app/api/files/download/output/c998ae90-d27a-4da9-802a-f14f734c2d2a/6249f72c-4c2f-4b81-8eb0-6662719122d7/output.mp4"
  );
});

test("extracts the output job id from R2 URLs when only the display URL is available", () => {
  expect(jobIdFromOutputSource(R2_OUTPUT_URL)).toBe("6249f72c-4c2f-4b81-8eb0-6662719122d7");
});

test("prefers explicit backend download URLs over presigned display URLs", () => {
  expect(apiDownloadUrl({
    apiBase: API,
    jobId: "",
    downloadUrl: "/api/files/download/output/session/job/output.mp4",
    source: R2_OUTPUT_URL,
  })).toBe("https://vision-sys.web.app/api/files/download/output/session/job/output.mp4");
});

test("prefers job id API downloads over direct source fetches", () => {
  expect(apiDownloadUrl({
    apiBase: API,
    jobId: "6249f72c-4c2f-4b81-8eb0-6662719122d7",
    source: R2_OUTPUT_URL,
  })).toBe("https://vision-sys.web.app/api/files/download/6249f72c-4c2f-4b81-8eb0-6662719122d7");
});

test("detects API URLs that need auth headers", () => {
  expect(isApiUrl("https://vision-sys.web.app/api/files/download/job", API)).toBe(true);
  expect(isApiUrl(R2_OUTPUT_URL, API)).toBe(false);
});

test("derives an API URL from the presigned R2 source when no job id or download url exists", () => {
  const url = apiDownloadUrl({ apiBase: API, jobId: "", downloadUrl: "", source: R2_OUTPUT_URL });
  expect(url).toBe(
    "https://vision-sys.web.app/api/files/download/output/c998ae90-d27a-4da9-802a-f14f734c2d2a/6249f72c-4c2f-4b81-8eb0-6662719122d7/output.mp4"
  );
  expect(isApiUrl(url, API)).toBe(true);
});

test("never returns a direct R2 URL when nothing maps to the API", () => {
  // An unparseable presigned source (no /outputs/ segment, no job id) must NOT
  // fall through to a direct cross-origin R2 fetch.
  const unmappable =
    "https://34c5468ebfcd71e2a958b25cfb0bde40.r2.cloudflarestorage.com/deplyzegpt-storage/misc/blob.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256";
  const url = apiDownloadUrl({ apiBase: API, jobId: "", downloadUrl: "", source: unmappable });
  expect(url).toBe("");
  expect(isApiUrl(url, API)).toBe(false);
});

test("ignores a download url that points off-origin and keeps it API-only", () => {
  // A malformed/absolute R2 download_url must be rejected, falling back to the
  // job id API route rather than fetching R2 directly.
  const url = apiDownloadUrl({
    apiBase: API,
    jobId: "6249f72c-4c2f-4b81-8eb0-6662719122d7",
    downloadUrl: R2_OUTPUT_URL,
    source: R2_OUTPUT_URL,
  });
  expect(url).toBe("https://vision-sys.web.app/api/files/download/6249f72c-4c2f-4b81-8eb0-6662719122d7");
  expect(isApiUrl(url, API)).toBe(true);
});
