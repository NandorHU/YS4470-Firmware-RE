"""Apply coordinator-checked lessons to the source-cited local review client."""
from pathlib import Path
import local_review_worker_v3 as worker
worker.SYSTEM += "\n\n" + Path(__file__).with_name("LESSONS.md").read_text(encoding="utf-8")
if __name__ == "__main__":
    worker.main()
