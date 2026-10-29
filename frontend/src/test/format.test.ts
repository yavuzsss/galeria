import { mediaUrlAt, searchUrl, type SearchResult } from "../api";
import { formatMs, formatTime, plural } from "../format";

test("formatTime", () => {
  expect(formatTime(0)).toBe("0:00");
  expect(formatTime(4.9)).toBe("0:04");
  expect(formatTime(75.4)).toBe("1:15");
  expect(formatTime(3725)).toBe("1:02:05");
  expect(formatTime(-3)).toBe("0:00");
});

test("formatMs and plural", () => {
  expect(formatMs(4.234)).toBe("4.2 ms");
  expect(formatMs(27.6)).toBe("28 ms");
  expect(plural(1, "photo")).toBe("1 photo");
  expect(plural(1200, "photo")).toBe("1,200 photos");
});

test("searchUrl encodes the query and omits the default filter", () => {
  expect(searchUrl("kedi kutuda", "all")).toBe("/api/search?q=kedi+kutuda&k=48");
  expect(searchUrl("ağaç & göl", "video", 10)).toBe(
    "/api/search?q=a%C4%9Fa%C3%A7+%26+g%C3%B6l&k=10&type=video",
  );
});

test("mediaUrlAt adds a media fragment for videos only", () => {
  const base = { media_url: "/api/media/7" } as SearchResult;
  expect(mediaUrlAt({ ...base, timestamp: 12.5 })).toBe("/api/media/7#t=12.5");
  expect(mediaUrlAt({ ...base, timestamp: null })).toBe("/api/media/7");
  expect(mediaUrlAt({ ...base, timestamp: 0 }, 30)).toBe("/api/media/7#t=30");
});
