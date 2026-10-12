import contextlib
import io
import sys
import unittest
from scripts.configure import run


class ConfigureTests(unittest.TestCase):
    def test_cli_unicode_output_does_not_break_secret_configuration(self):
        with contextlib.redirect_stdout(io.StringIO()):
            run([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(bytes([226,143,169]))'])


if __name__ == '__main__':
    unittest.main()
