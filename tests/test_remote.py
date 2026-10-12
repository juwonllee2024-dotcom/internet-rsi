import tempfile
import unittest
from pathlib import Path
from rsi.remote import RemoteStore


class RemoteTests(unittest.TestCase):
    def test_failed_upload_keeps_private_checkpoint_for_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            store=RemoteStore('http://127.0.0.1:9999','private-test-token-12345678',outbox=Path(directory))
            store.request=lambda *args: (_ for _ in ()).throw(RuntimeError('network unavailable'))
            with self.assertRaises(RuntimeError):
                store.checkpoint(3,'lease-token',{'samples':{'baseline':{'a':{'passed':True}}}})
            packet=list(Path(directory).glob('*.json'))
            self.assertEqual(len(packet),1)
            self.assertIn('lease-token',packet[0].read_text())
