import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { JobStatus, SearchResponse, SearchResult, Stats } from "../api";
import { App } from "../App";

const photo: SearchResult = {
  id: 1,
  kind: "photo",
  name: "beach.jpg",
  path: "/lib/beach.jpg",
  score: 0.31,
  thumb_url: "/api/thumbs/aaaaaaaaaaaaaaaaaaaa.jpg",
  media_url: "/api/media/1",
  timestamp: null,
  width: 800,
  height: 600,
  duration: null,
  moments: [],
};

const video: SearchResult = {
  ...photo,
  id: 2,
  kind: "video",
  name: "trip.mp4",
  path: "/lib/trip.mp4",
  score: 0.29,
  media_url: "/api/media/2",
  timestamp: 24,
  duration: 60,
  moments: [
    { timestamp: 24, score: 0.29, thumb_url: "/api/thumbs/bbbbbbbbbbbbbbbbbbbb.jpg" },
    { timestamp: 42, score: 0.25, thumb_url: "/api/thumbs/cccccccccccccccccccc.jpg" },
  ],
};

const stats: Stats = {
  photos: 1,
  videos: 1,
  vectors: 3,
  encoder: "clip",
  roots: ["/lib"],
  allowed_roots: [],
};

function searchResponse(
  results: SearchResult[],
  query = "beach",
  min_score: number | null = null,
): SearchResponse {
  return { query, took_ms: 6.4, encode_ms: 6.1, search_ms: 0.3, total_vectors: 3, min_score, results };
}

type Handler = (url: URL, init?: RequestInit) => unknown;

function mockApi(handlers: Record<string, Handler>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, "http://localhost");
      calls.push(`${init?.method ?? "GET"} ${url.pathname}${url.search}`);
      const handler = handlers[url.pathname];
      if (!handler) return new Response("{}", { status: 404 });
      const body = handler(url, init);
      if (body instanceof Response) return body;
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  return calls;
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("searching shows results, timing and keeps the query in the URL", async () => {
  mockApi({ "/api/stats": () => stats, "/api/search": () => searchResponse([photo, video]) });
  render(<App />);

  expect(await screen.findByText("1 photo · 1 video")).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox"), "beach");

  expect(await screen.findByRole("button", { name: "Open beach.jpg" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Open trip.mp4, video, best match at 0:24/ })).toBeInTheDocument();
  expect(screen.getByText("6.4 ms")).toBeInTheDocument();
  expect(window.location.search).toBe("?q=beach");
});

test("typing quickly sends one request for the final query", async () => {
  const calls = mockApi({
    "/api/stats": () => stats,
    "/api/search": (url) => searchResponse([photo], url.searchParams.get("q")!),
  });
  render(<App />);
  await userEvent.type(screen.getByRole("searchbox"), "sunset");
  await screen.findByRole("button", { name: "Open beach.jpg" });
  expect(calls.filter((c) => c.includes("/api/search"))).toEqual(["GET /api/search?q=sunset&k=48"]);
});

test("opening a video result plays it from the matching second", async () => {
  mockApi({ "/api/stats": () => stats, "/api/search": () => searchResponse([photo, video]) });
  window.history.replaceState(null, "", "/?q=beach");
  render(<App />);

  await userEvent.click(await screen.findByRole("button", { name: /Open trip.mp4/ }));
  const dialog = screen.getByRole("dialog", { name: "trip.mp4" });
  expect(dialog.querySelector("video")).toHaveAttribute("src", "/api/media/2#t=24");
  expect(within(dialog).getByRole("button", { name: "Jump to 0:42" })).toBeInTheDocument();

  await userEvent.keyboard("{ArrowLeft}");
  expect(screen.getByRole("dialog", { name: "beach.jpg" }).querySelector("img")).toHaveAttribute(
    "src",
    "/api/media/1",
  );
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("the type filter is sent to the API and stored in the URL", async () => {
  const calls = mockApi({ "/api/stats": () => stats, "/api/search": () => searchResponse([video]) });
  window.history.replaceState(null, "", "/?q=trip");
  render(<App />);
  await screen.findByRole("button", { name: /Open trip.mp4/ });

  await userEvent.click(screen.getByRole("radio", { name: "Videos" }));
  await waitFor(() => expect(calls).toContain("GET /api/search?q=trip&k=48&type=video"));
  expect(window.location.search).toBe("?q=trip&type=video");
});

test("an empty index invites the user to index a folder", async () => {
  mockApi({ "/api/stats": () => ({ ...stats, photos: 0, videos: 0, vectors: 0, roots: [] }) });
  render(<App />);
  expect(await screen.findByText("Nothing indexed yet")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Index a folder" }));
  expect(screen.getByRole("complementary", { name: "Index a folder" })).toBeInTheDocument();
});

test("the indexing panel offers the server's allowed folder (Docker's /media)", async () => {
  mockApi({
    "/api/stats": () => ({ ...stats, vectors: 0, roots: [], allowed_roots: ["/media"] }),
    "/api/index/status": () => ({ state: "idle", folder: null, done: 0, total: 0, current: null, report: null, error: null }),
  });
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: "Index a folder" }));
  expect(screen.getByLabelText("Folder path on the server")).toHaveValue("/media");
  expect(screen.getByText("Allowed: /media")).toBeInTheDocument();
});

test("API errors are shown, not swallowed", async () => {
  mockApi({
    "/api/stats": () => stats,
    "/api/search": () => new Response(JSON.stringify({ detail: "index is corrupt" }), { status: 500 }),
  });
  window.history.replaceState(null, "", "/?q=x");
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Search failed: index is corrupt");
});

test("indexing panel starts a job, shows progress and the final report", async () => {
  const states: JobStatus[] = [
    { state: "running", folder: "/lib", done: 1, total: 4, current: "/lib/a.jpg", report: null, error: null },
    {
      state: "done",
      folder: "/lib",
      done: 4,
      total: 4,
      current: null,
      error: null,
      report: {
        root: "/lib", added: 3, updated: 0, removed: 0, unchanged: 1, vectors_added: 5,
        frames_sampled: 6, frames_kept: 2, failed: ["/lib/bad.jpg"], seconds: 1.25,
      },
    },
  ];
  // Status polls answer in order: idle (panel opens), running, then done from there on.
  const statusSequence: JobStatus[] = [{ ...states[0], state: "idle" }, states[0], states[1]];
  let polls = 0;
  const calls = mockApi({
    "/api/stats": () => stats,
    "/api/index": () => states[0],
    "/api/index/status": () => statusSequence[Math.min(polls++, statusSequence.length - 1)],
  });
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: "Index folder" }));
  const panel = screen.getByRole("complementary", { name: "Index a folder" });

  await userEvent.click(within(panel).getByRole("button", { name: "Start indexing" }));
  expect(calls).toContain("POST /api/index");
  expect(await within(panel).findByText("1 / 4 files")).toBeInTheDocument();
  expect(await within(panel).findByText("Done in 1.3 s", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(within(panel).getByText("2 of 6 video frames kept")).toBeInTheDocument();
  expect(within(panel).getByText("1 file could not be read")).toBeInTheDocument();
  // Finishing refreshes the header stats.
  await waitFor(() => expect(calls.filter((c) => c === "GET /api/stats").length).toBeGreaterThan(1));
});

test("an empty result under a score cutoff says why", async () => {
  mockApi({ "/api/stats": () => stats, "/api/search": () => searchResponse([], "space shuttle", 0.28) });
  window.history.replaceState(null, "", "/?q=space+shuttle");
  render(<App />);
  expect(await screen.findByText(/Nothing scores above the 0.28 cutoff/)).toBeInTheDocument();
  expect(screen.getByText(/cutoff 0.28/, { selector: ".status__detail" })).toBeInTheDocument();
});
