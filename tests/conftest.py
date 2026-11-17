import os
import tempfile

os.environ.setdefault("DEMO_TOKEN", "test-token")
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.sqlite3"))
