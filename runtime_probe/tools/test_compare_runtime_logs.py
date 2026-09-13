"""Host-only tests using synthetic values reported for the unpaired baseline."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from compare_runtime_logs import activity, compare, parse_log, snapshot


FIXTURE = Path(__file__).parent / "fixtures" / "unpaired_baseline_synthetic.log"


class CompareRuntimeLogsTest(unittest.TestCase):
    def test_unpaired_fixture(self):
        capture = parse_log(FIXTURE)
        self.assertEqual(capture["header"]["hos"], "22.5.0")
        settings, pairing, sample = snapshot(capture, "application_started")
        self.assertEqual(len(settings["blob_bytes"]), 0x44)
        self.assertEqual(settings["blob_bytes"][:12], bytes.fromhex("000101000000000000000000"))
        self.assertEqual(settings["blob_bytes"][12:], bytes.fromhex("0000000600010200") * 7)
        self.assertEqual(pairing["pairing_active"], "0")
        self.assertEqual(pairing["last_updated_posix_raw"], "71822")
        self.assertEqual(sample["spent_raw"], "0x0000000000000000")
        self.assertEqual(activity(capture)[0], "not observed")

    def compare_with(self, paired_text):
        with tempfile.TemporaryDirectory() as directory:
            paired = Path(directory) / "paired.log"
            paired.write_text(paired_text)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                compare(FIXTURE, paired)
            return output.getvalue()

    def test_identical_blob_with_paired_accounting(self):
        paired = FIXTURE.read_text().replace("pairing_active=0", "pairing_active=1")
        before, after = paired.rsplit("spent_raw=0x0000000000000000", 1)
        paired = before + "spent_raw=0x0000000000000001" + after
        output = self.compare_with(paired)
        self.assertIn("application_started 0x44-byte differences:\n  none", output)
        self.assertIn("accounting observed only in paired capture=True", output)
        self.assertIn("0x44 settings blob differs=False", output)

    def test_exact_byte_difference_and_both_changed(self):
        paired = FIXTURE.read_text().replace("pairing_active=0", "pairing_active=1")
        paired = paired.replace("blob=00010100", "blob=01010100")
        before, after = paired.rsplit("spent_raw=0x0000000000000000", 1)
        paired = before + "spent_raw=0x0000000000000001" + after
        output = self.compare_with(paired)
        self.assertIn("offset 0x00: unpaired=0x00 paired=0x01", output)
        self.assertIn("both settings and runtime behavior differ=True", output)

    def test_rejects_truncated_blob(self):
        text = FIXTURE.read_text().replace("blob=00010100", "blob=0001010", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.log"
            path.write_text(text)
            with self.assertRaisesRegex(ValueError, "exactly 0x44"):
                parse_log(path)

    def test_nonzero_but_flat_spent_is_not_counting(self):
        text = FIXTURE.read_text().replace("spent_raw=0x0000000000000000",
                                           "spent_raw=0x0000000000000001")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flat.log"
            path.write_text(text)
            self.assertEqual(activity(parse_log(path))[0], "not observed")

    def test_new_pid_is_separate_interval(self):
        text = FIXTURE.read_text()
        text = text.replace("sample=2 time=2026-09-13T00:00:10 application_query_rc=0x00000000 "
                            "application_process_present=1 application_pid=0x0000000000001234",
                            "sample=2 time=2026-09-13T00:00:10 application_query_rc=0x00000000 "
                            "application_process_present=1 application_pid=0x0000000000005678")
        before, after = text.rsplit("spent_raw=0x0000000000000000", 1)
        text = before + "spent_raw=0x0000000000000001" + after
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "second_pid.log"
            path.write_text(text)
            self.assertEqual(activity(parse_log(path))[0], "indeterminate")


if __name__ == "__main__":
    unittest.main()
