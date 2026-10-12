import unittest
try:
    from training.lora import admission
except ImportError:
    admission=None


class TrainingTests(unittest.TestCase):
    def test_small_laptop_defers_training_without_claiming_success(self):
        self.assertIsNotNone(admission,'training resource gate not implemented')
        result=admission({'base_model':'Qwen/Qwen3.5-2B','model_revision':'a'*40,'dataset_sha256':'b'*64,'max_steps':20},False,1)
        self.assertFalse(result['eligible'])
        self.assertIn('CUDA',result['reason'])

    def test_model_identity_dataset_and_budget_are_required(self):
        self.assertIsNotNone(admission,'training resource gate not implemented')
        valid={'base_model':'Qwen/Qwen3.5-2B','model_revision':'a'*40,'dataset_sha256':'b'*64,'max_steps':20}
        self.assertTrue(admission(valid,True,8)['eligible'])
        for override in [{'base_model':'other'},{'max_steps':100000},{'dataset_sha256':'mutable'},{'model_revision':'main'}]:
            with self.assertRaises(ValueError):
                admission(dict(valid,**override),True,80)
