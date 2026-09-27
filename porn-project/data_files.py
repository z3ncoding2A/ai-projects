"""
Shared write helpers for the JSON/text data files (videos.json, categories.json,
first_seen.json, blacklist.txt, ...), used by both serve.py and generate_grid.py.

- atomic_write_text(): readers (serve.py's GET handlers) never take a lock, so
  every write must publish a whole file in one os.replace.
- data_file_lock(): serializes read-modify-write cycles across *processes*. A
  threading lock only covers serve.py's own request threads; it can't stop the
  server reading videos.json, losing a race to a scrape that replaces it, and
  then writing its stale copy back over the fresh one.
"""
import contextlib
import fcntl
import os
import tempfile
import threading

LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".data.lock")

# os.umask() can only be read by setting it, which isn't thread-safe, so read it
# once at import time (before serve.py starts its request threads).
_UMASK = os.umask(0)
os.umask(_UMASK)
_FILE_MODE = 0o666 & ~_UMASK

_thread_lock = threading.Lock()


@contextlib.contextmanager
def data_file_lock():
    """
    Hold around a read-modify-write of a data file. Never hold it across a
    scrape or other slow network work -- plain reads don't need it.
    """
    # flock() alone would also exclude threads that open the file separately;
    # the in-process lock just keeps same-process contention off the filesystem.
    with _thread_lock:
        with open(LOCK_PATH, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def atomic_write_text(path, text):
    # Unique tmp name per write: a shared "<path>.tmp" lets two writers truncate
    # and interleave into the same file, so one rename can publish a half-written
    # blob.
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(os.path.abspath(path)),
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # mkstemp creates 0600 and os.replace carries that onto the data
            # file; use the mode a plain open() would have given it instead.
            os.fchmod(f.fileno(), _FILE_MODE)
            f.write(text)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
