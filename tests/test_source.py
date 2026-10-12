import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from rsi.runtime import source_dirty


class SourceTests(unittest.TestCase):
    def test_dirty_runtime_is_detected_without_blocking_document_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'rsi').mkdir();source=root/'rsi'/'runtime.py';source.write_text('version=1\n')
            prefix=['rtk','proxy'] if shutil.which('rtk') else []
            def git(*args):
                subprocess.run(prefix+['git','-C',directory,*args],check=True,capture_output=True)
            git('init');git('add','rsi');git('-c','user.name=Infrastructure test','-c','user.email=test@example.invalid','commit','-m','fixture')
            self.assertFalse(source_dirty(root))
            (root/'README.md').write_text('documentation edit')
            self.assertFalse(source_dirty(root))
            source.write_text('version=2\n')
            self.assertTrue(source_dirty(root))
