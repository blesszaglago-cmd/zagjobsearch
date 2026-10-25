import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "source_lab", Path(__file__).resolve().parents[1] / "source_lab.py"
)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class SourceLabTests(unittest.TestCase):
    def test_three_engines_agree_without_network(self):
        fixtures = {
            "ghana-current-jobs": '<h3 class="special">Engineer</h3><div class="summary"><div class="row">Accra</div></div><div class="content text-justify">Ghana role</div>',
            "jobweb-ghana": '<h1 class="title">Engineer at Test</h1><div class="section_header"><div class="date"><strong>25 Oct 2026</strong></div></div><div class="section single"><div class="section_content"><font>Ghana role</font></div></div>',
        }
        with patch(
            "socket.socket.connect", side_effect=AssertionError("No network allowed")
        ):
            for profile, html in fixtures.items():
                result = lab.compare(html, profile)
                self.assertTrue(result["agreement"])
                self.assertTrue(result["required_selectors_found"])
                self.assertFalse(result["publishable"])

    def test_empty_consensus_never_establishes_source_validity(self):
        result = lab.compare("<h1>New unknown page format</h1>", "jobweb-ghana")
        self.assertTrue(result["agreement"])
        self.assertFalse(result["required_selectors_found"])
        self.assertFalse(result["publishable"])

    def test_autoscraper_learns_candidates_offline_and_excludes_advert(self):
        html = '<div class="roles"><article><h2>Field Officer</h2></article><article><h2>Teacher</h2></article></div><aside><h2>Advert</h2></aside>'
        with patch(
            "requests.get", side_effect=AssertionError("No network allowed")
        ), patch(
            "socket.socket.connect", side_effect=AssertionError("No network allowed")
        ):
            result = lab.learn(html, ["Field Officer"])
        self.assertIn("Field Officer", result["matches"])
        self.assertIn("Teacher", result["matches"])
        self.assertNotIn("Advert", result["matches"])
        self.assertFalse(result["publishable"])

    def test_reports_are_private_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            lab.write_report(path, {"publishable": False})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                lab.write_report(path, {})

    def test_invalid_inputs_are_rejected(self):
        for examples in [[], [""], ["a" * 2001], ["x"] * 21]:
            with self.assertRaises(ValueError):
                lab.learn("<p>hello</p>", examples)
        with self.assertRaises(ValueError):
            lab.compare("<p>test</p>", "unknown")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.html"
            path.write_bytes(b"x" * (lab.MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                lab.read_html(path)
