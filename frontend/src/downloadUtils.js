const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function encodePathSegment(value) {
  return encodeURIComponent(value || "");
}

function apiOrigin(apiBase) {
  return new URL(apiBase, window.location.origin).origin;
}

function absoluteDownloadUrl(downloadUrl, apiBase) {
  if (!downloadUrl) return "";
  if (downloadUrl.startsWith("/")) {
    return new URL(downloadUrl, apiOrigin(apiBase)).toString();
  }
  return new URL(downloadUrl, window.location.origin).toString();
}

export function outputPathDownloadUrl(source, apiBase) {
  if (!source || !apiBase) return "";

  try {
    const parsed = new URL(source, window.location.origin);
    const parts = parsed.pathname.split("/").filter(Boolean);
    const outputIndex = parts.indexOf("outputs");
    if (outputIndex === -1 || parts.length < outputIndex + 5) {
      return "";
    }

    const sessionId = parts[outputIndex + 2];
    const jobId = parts[outputIndex + 3];
    const filename = parts[outputIndex + 4];
    if (!sessionId || !jobId || !filename) {
      return "";
    }

    return [
      apiBase.replace(/\/$/, ""),
      "files",
      "download",
      "output",
      encodePathSegment(sessionId),
      encodePathSegment(jobId),
      encodePathSegment(filename),
    ].join("/");
  } catch {
    return "";
  }
}

export function jobIdFromOutputSource(source) {
  if (!source) return "";

  try {
    const parsed = new URL(source, window.location.origin);
    const parts = parsed.pathname.split("/").filter(Boolean);
    const outputIndex = parts.indexOf("outputs");
    if (outputIndex === -1) {
      return "";
    }

    const outputParts = parts.slice(outputIndex + 1);
    const uuids = outputParts.filter(part => UUID_PATTERN.test(part));
    return uuids.length ? uuids[uuids.length - 1] : "";
  } catch {
    return "";
  }
}

export function apiDownloadUrl({ apiBase, jobId, downloadUrl, source }) {
  if (downloadUrl) {
    const absolute = absoluteDownloadUrl(downloadUrl, apiBase);
    if (isApiUrl(absolute, apiBase)) {
      return absolute;
    }
  }

  if (jobId) {
    return `${apiBase.replace(/\/$/, "")}/files/download/${encodePathSegment(jobId)}`;
  }

  const outputDownloadUrl = outputPathDownloadUrl(source, apiBase);
  if (outputDownloadUrl) {
    return outputDownloadUrl;
  }

  const parsedJobId = jobIdFromOutputSource(source);
  if (parsedJobId) {
    return `${apiBase.replace(/\/$/, "")}/files/download/${encodePathSegment(parsedJobId)}`;
  }

  // Never fall back to a raw R2 / cross-origin URL: the browser must only ever
  // fetch the same-origin authenticated API. If we cannot derive an API URL,
  // return empty so the caller surfaces an inline download error instead of
  // triggering a CORS-blocked direct R2 fetch.
  return "";
}

export function isApiUrl(url, apiBase) {
  if (!url || !apiBase) return false;
  try {
    const parsed = new URL(url, window.location.origin);
    const api = new URL(apiBase, window.location.origin);
    return parsed.origin === api.origin && parsed.pathname.startsWith(api.pathname.replace(/\/$/, ""));
  } catch {
    return false;
  }
}
