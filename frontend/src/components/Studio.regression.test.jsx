process.env.REACT_APP_BACKEND_URL = "http://localhost:8000";
process.env.REACT_APP_ENABLE_LOCATE_ANYTHING = "true";
process.env.REACT_APP_ENABLE_LOCATE_ANYTHING_VIDEO = "true";
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const React = require("react");
const { act } = require("react");
const { createRoot } = require("react-dom/client");

const axios = require("axios");
const Studio = require("./Studio").default;

jest.mock("axios", () => ({
  get: jest.fn(),
  post: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
}));

jest.mock("firebase/firestore", () => ({
  doc: jest.fn(() => ({})),
  onSnapshot: jest.fn(() => jest.fn()),
}));

jest.mock("../firebase", () => ({ db: {} }));

jest.mock("./Sidebar", () => function Sidebar() {
  return <aside data-testid="sidebar" />;
});

jest.mock("./ChatInputBar", () => function ChatInputBar(props) {
  global.latestChatInputProps = props;
  return (
    <div
      data-testid="chat-input"
      data-selected-model={props.selectedModel}
      data-disabled-models={(props.disabledModelIds || []).join(",")}
    >
      <button type="button" data-testid="mock-file-select" onClick={() => props.onFileSelect(global.mockSelectedFile)}>
        file
      </button>
      <button type="button" data-testid="mock-send" onClick={props.onSend}>
        send
      </button>
    </div>
  );
});

function createUser() {
  return {
    uid: "uid-1",
    email: "user@example.com",
    getIdToken: jest.fn().mockResolvedValue("token"),
  };
}

function setupAxios() {
  axios.get.mockImplementation((url) => {
    if (url.endsWith("/api/sessions")) {
      return Promise.resolve({ data: { sessions: [] } });
    }
    return Promise.resolve({ data: {} });
  });
  axios.post.mockImplementation((url) => {
    if (url.endsWith("/api/upload")) {
      const isVideo = global.mockSelectedFile?.type?.startsWith("video/");
      return Promise.resolve({
        data: {
          session_id: "session-1",
          url: `/api/files/uploads/job-1/input.${isVideo ? "mp4" : "png"}`,
          filename: global.mockSelectedFile?.name || "input.png",
          file_type: isVideo ? "video" : "image",
        },
      });
    }
    if (url.endsWith("/api/analyze/image")) {
      return Promise.resolve({
        data: {
          session_id: "session-1",
          type: "text",
          content: "done",
          suggestions: [],
        },
      });
    }
    if (url.endsWith("/api/analyze/video")) {
      return Promise.resolve({ data: { session_id: "session-1", job_id: "job-1", status: "queued" } });
    }
    return Promise.resolve({ data: {} });
  });
}

async function renderStudio() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Studio user={createUser()} onSignOut={() => {}} onProfileUpdate={() => {}} />);
  });
  return { container, root };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("Studio regressions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupAxios();
    global.latestChatInputProps = null;
    global.mockSelectedFile = null;
    global.URL.createObjectURL = jest.fn(() => "blob:local-preview");
    Element.prototype.scrollIntoView = jest.fn();
    window.localStorage.clear();
  });

  test("renders the user image message after sending an uploaded image", async () => {
    const { container, root } = await renderStudio();

    global.mockSelectedFile = new File(["image"], "street.png", { type: "image/png" });
    await act(async () => {
      container.querySelector('[data-testid="mock-file-select"]').click();
    });
    await flush();

    await act(async () => {
      container.querySelector('[data-testid="mock-send"]').click();
    });
    await flush();

    expect(container.querySelector('[data-testid="user-message"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="user-message-image"]')?.getAttribute("src")).toBe("blob:local-preview");

    await act(async () => root.unmount());
  });

  test("keeps Locate selectable when a video is uploaded", async () => {
    const { container, root } = await renderStudio();

    await act(async () => {
      global.latestChatInputProps.onModelSelect("locate-anything");
    });

    global.mockSelectedFile = new File(["video"], "clip.mp4", { type: "video/mp4" });
    await act(async () => {
      container.querySelector('[data-testid="mock-file-select"]').click();
    });
    await flush();

    expect(global.latestChatInputProps.selectedModel).toBe("locate-anything");
    expect(global.latestChatInputProps.disabledModelIds).not.toContain("locate-anything");

    await act(async () => root.unmount());
  });
});
