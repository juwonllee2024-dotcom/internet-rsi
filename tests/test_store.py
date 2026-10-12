import tempfile
import unittest
from pathlib import Path
try:
    from rsi.store import Store
except ImportError:
    Store = None


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Store, 'persistent store not implemented')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.sqlite'
        self.now = 1000
        self.store = Store(self.path, clock=lambda: self.now, lease_seconds=60)

    def test_checkpoints_survive_restart(self):
        job = self.store.claim('one')
        self.store.checkpoint(job['id'], job['token'], {'candidate': {'hypothesis': 'test'}})
        restarted = Store(self.path, clock=lambda: self.now, lease_seconds=60)
        resumed = restarted.claim('one')
        self.assertEqual(job['token'], resumed['token'])
        self.assertEqual(resumed['payload']['candidate']['hypothesis'], 'test')
        self.assertIsNone(restarted.claim('two'))

    def test_expired_worker_is_fenced_and_work_preserved(self):
        old = self.store.claim('one')
        self.store.checkpoint(old['id'], old['token'], {'progress': 4})
        self.now += 61
        new = self.store.claim('two')
        self.assertEqual(new['payload']['progress'], 4)
        self.assertNotEqual(new['token'], old['token'])
        with self.assertRaises(ValueError):
            self.store.checkpoint(old['id'], old['token'], {'progress': 0})

    def test_completion_is_idempotent_and_queues_next_cycle(self):
        job = self.store.claim('one')
        report = {'decision': {'accepted': False}, 'candidate_config': None, 'samples': {}}
        first = self.store.finish(job['id'], job['token'], report)
        self.assertEqual(first, self.store.finish(job['id'], job['token'], report))
        self.assertEqual(self.store.status()['validated']['version'], 1)
        self.assertEqual(self.store.claim('one')['id'], job['id'] + 1)

    def test_partial_evidence_cannot_promote(self):
        job = self.store.claim('one')
        with self.assertRaises(ValueError):
            self.store.finish(job['id'], job['token'], {'decision': {'accepted': True}, 'samples': {}})
        self.assertEqual(self.store.status()['validated']['version'], 1)

    def test_pause_blocks_claim_and_resume_preserves_task(self):
        self.store.pause(True)
        self.assertIsNone(self.store.claim('one'))
        self.store.pause(False)
        self.assertIsNotNone(self.store.claim('one'))


if __name__ == '__main__':
    unittest.main()
