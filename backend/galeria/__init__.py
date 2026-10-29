import os
import sys

if sys.platform == "darwin":
    # The macOS wheels of torch and faiss each bundle their own copy of LLVM libomp, so two
    # OpenMP runtimes end up in one process. Without the steps below, loading model weights
    # segfaults when faiss is imported first, and faiss searches abort ("OMP: Error #15") or
    # segfault once torch has run. Fix, verified on the pinned versions:
    #   1. load torch before faiss (here; every faiss user lives in this package),
    #   2. tell libomp a second copy is expected (here),
    #   3. keep faiss single-threaded so its runtime never starts a thread pool. OpenMP thread
    #      counts are per calling thread, so VectorStore does this in every thread it runs in.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    import torch  # noqa: F401
