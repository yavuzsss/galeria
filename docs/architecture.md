# Architecture and design notes

The README has the overview diagrams. This page records *why* things are the way they are,
including the bugs that shaped them.

## Data model

Two stores, kept in step by the indexer:

| Store | Holds |
|---|---|
| FAISS `IndexIDMap2(IndexFlatIP)` | One L2-normalized 512-d vector per photo or kept video frame |
| SQLite `files` | Path, kind, size, mtime, dimensions, duration |
| SQLite `vectors` | `id` (= the FAISS id), `file_id`, `timestamp` (videos), thumbnail name |
| SQLite `roots`, `meta` | Indexed folders (media is only served from inside them); encoder name |

Using the SQLite row id as the FAISS id means a search hit maps straight to its metadata, and
deleting a file deletes exactly its vectors (`ON DELETE CASCADE`, then `remove_ids`).

The encoder's name is stored in `meta`. Opening an index with a different model raises
`EncoderMismatchError` instead of silently mixing vectors from two embedding spaces.

## Why exact search

Inner product over normalized vectors is cosine similarity. A brute-force scan of 100k 512-d
vectors takes a few milliseconds, which is smaller than encoding the query, and it has perfect
recall. An approximate index (IVF, HNSW) only pays off well past that size; swapping one in is a
change inside `VectorStore`.

## Indexing

- **Incremental.** A file is unchanged when size and mtime match. Changed files are removed and
  re-added like new ones; files gone from disk are removed with their thumbnails.
- **Cheap decoding.** JPEGs are opened with Pillow's `draft()` at ≤512 px instead of full
  resolution — CLIP only sees 224 px, and decoding 24-megapixel originals dominated indexing
  time. EXIF orientation is applied, and the original size is kept for the UI.
- **Thumbnails** are named by a hash of path + mtime (+ timestamp for frames), so an edited
  file gets a new URL and the API can serve thumbnails as immutable.
- **Our own thumbnails** are excluded from scanning, in case the data dir lives inside an
  indexed folder.
- **Crash safety.** SQLite commits per file; FAISS is saved every 20 batches and at the end,
  each time to a temp file renamed into place. After a crash SQLite can know about vectors
  FAISS lost, so every run starts with `reconcile()`: vectors without metadata are dropped, and
  files whose vectors are missing are forgotten so they get re-indexed.

## Video

- **Sampling.** PyAV (bundled FFmpeg, no system dependency) decodes sequentially and keeps the
  first frame at or after each 2 s mark. Seeking per sample would re-decode up to a whole
  keyframe interval each time; sequential decoding costs the same for any interval. Videos that
  would exceed 900 samples get a wider interval.
- **Near-duplicate frames.** Each frame is compared with the last *kept* frame and dropped at
  cosine ≥ 0.95. Comparing with the last kept frame (not the previous one) means a slow pan
  still adds a frame once it has drifted far enough. On a 30 s slideshow with a slow zoom, 15
  samples became 5 vectors, one per scene; across the eval videos, 107 became 73.
- **Search-time grouping.** Many frames of one video can match. The searcher fetches 4× k
  candidates, keeps the best hit per file (its timestamp is the result's timestamp) and lists the
  other hits as "moments". If fewer than k files come back it widens the window — unless a
  `min_score` cutoff is set and the window already reached below it, since hits arrive sorted
  and nothing further can qualify.
- **Playback.** The UI opens `/api/media/{id}#t=<seconds>`; the media endpoint supports HTTP
  Range (and nginx forwards it unbuffered), so the browser seeks without downloading the file.

## Concurrency

The API serves searches while a background thread indexes.

- Endpoints are plain `def`, so FastAPI runs them in its thread pool and the event loop keeps
  serving thumbnails and video bytes.
- The encoder has one lock per model: torch modules aren't safe to call from several threads,
  but separate locks let a search use the text model while the indexer holds the image model.
- `VectorStore` serializes FAISS calls with a lock (add during search is unsafe); SQLite uses
  one connection, shared and guarded by a lock, in WAL mode.
- Measured: 243 searches ran while 220 photos were indexed through the API, with no errors
  and median latency unchanged (5.2 ms vs. 6.3 ms idle).

## The macOS OpenMP bugs

Unit tests use a fake encoder, so they never ran torch and faiss in one process. The first
real-model run crashed, and it took three fixes, each found by isolating one variable:

1. **Segfault while loading weights.** The macOS wheels of torch and faiss each bundle their own
   `libomp`. With faiss imported first, torch crashed loading the text model; with torch first, it
   didn't. Fix: `galeria/__init__.py` imports torch before anything imports faiss.
2. **`OMP: Error #15` on the first search.** Import order alone wasn't enough: both runtimes still
   initialized. Fix: set `KMP_DUPLICATE_LIB_OK` (libomp's documented switch for this case) and run
   faiss single-threaded, so its runtime never starts a thread pool. A flat-index search for one
   query isn't parallelized anyway, so nothing is lost.
3. **Segfault in API worker threads.** OpenMP thread counts are *per calling thread*: the main
   thread was pinned, FastAPI's worker threads weren't. A four-thread script reproduced it (exit
   139 unpinned, clean pinned). Fix: `VectorStore` pins every thread that touches faiss, once,
   via a thread-local flag.

All three are no-ops off macOS; the Docker image (Linux) never needed them.

## Query latency

Encoding the query dominates; the FAISS scan and the SQLite lookup are each well under 1 ms.
The text model runs on the CPU by default even on Apple Silicon: MPS compiles kernels per new
input length, which gave a 128 ms p95 versus 7.3 ms on CPU, with identical results (see
[eval/results/latest.md](../eval/results/latest.md)). The API also runs one warm-up pass at
startup so the first real query isn't the slow one.

## Security

Galeria serves files from disk, so the boundaries matter:

- The API binds to `127.0.0.1` by default; in Docker only nginx is published, also on localhost.
- `GALERIA_ALLOWED_ROOTS` limits what `POST /api/index` accepts (Docker sets it to `/media`,
  which is mounted read-only).
- `/api/media/{id}` only serves paths from the database that are inside an indexed root.
- Thumbnail names must match `^[0-9a-f]{20}\.jpg$` before the filesystem is touched.
- The container runs as an unprivileged user.

There is no authentication; it's a single-user, local tool.

## Frontend

- Search-as-you-type is debounced (250 ms) and each new query aborts the request in flight, so a
  slow answer to an old query can never overwrite a newer one.
- Query and filter live in the URL: searches are shareable and the back button works. Typing
  replaces the history entry; committing (Enter, chips, filters) pushes one.
- While a query loads, the previous results stay on screen, dimmed, instead of flashing empty.
- The viewer moves focus into the dialog, closes on Escape, steps with ←/→ and returns focus to
  the card it was opened from. (It does not trap Tab yet.)

## Docker

- On Linux, `torch` resolves from PyTorch's CPU-only index (`[tool.uv.sources]` in
  `pyproject.toml`). The default PyPI wheel pulls in CUDA libraries: the lockfile lost 73 nvidia
  packages and triton. `torch` is a direct dependency for this reason alone — uv only applies
  sources to direct dependencies.
- Dependencies install in their own layer before the source is copied, so code changes rebuild
  in seconds.
- Model weights go to a volume (`HF_HOME=/models`), downloaded once; the healthcheck allows three
  minutes for that first start and only passes once the model is warm.
- Image sizes: frontend 93 MB; backend 2.1 GB, of which torch (CPU) is 683 MB and most of the
  rest is scipy, scikit-learn and transformers pulled in by sentence-transformers.
