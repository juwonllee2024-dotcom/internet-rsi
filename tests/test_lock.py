import tempfile
import unittest
from pathlib import Path
try:
    from rsi.lock import ClientLock
except ImportError:
    ClientLock=None


class LockTests(unittest.TestCase):
    def test_only_one_inference_client_per_checkout(self):
        self.assertIsNotNone(ClientLock,'process exclusion not implemented')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'client.lock'
            with ClientLock(path):
                with self.assertRaises(RuntimeError):
                    with ClientLock(path):pass
            with ClientLock(path):pass
