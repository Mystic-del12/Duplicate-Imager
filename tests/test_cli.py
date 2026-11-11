"""CLI validation for duplicate_photo_remover.

--threads 0 (or negative) used to reach ThreadPoolExecutor and die with
"ValueError: max_workers must be greater than 0". It is now rejected by
argparse (exit 2) before anything is scanned.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duplicate_photo_remover as dpr  # noqa: E402


class TestThreadsValidation:
    @pytest.mark.parametrize("bad", ["0", "-2"])
    def test_non_positive_threads_exit_2(self, monkeypatch, tmp_path, capsys, bad):
        monkeypatch.setattr(
            sys, "argv", ["duplicate_photo_remover.py", str(tmp_path), "--threads", bad]
        )
        with pytest.raises(SystemExit) as exc:
            dpr.main()
        assert exc.value.code == 2
        assert "positive integer" in capsys.readouterr().err

    def test_valid_threads_scan_empty_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            sys, "argv", ["duplicate_photo_remover.py", str(tmp_path), "--threads", "2"]
        )
        assert dpr.main() is None
