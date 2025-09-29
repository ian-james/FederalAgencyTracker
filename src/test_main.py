import tempfile
from pathlib import Path
from main import main

def test_main_end_to_end():
    """
    End-to-end test for the CLI using temporary directories.
    Downloads the PDF and searches for patterns.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "downloads"
        out_dir.mkdir(parents=True, exist_ok=True)
        results_file = Path(tmpdir) / "results.txt"

        argv = [
            "https://public-inspection.federalregister.gov/2025-15819.pdf",
            "--out-dir", str(out_dir),
            "--targets", "./search_args/test_regex.txt",
            "--results-file", str(results_file),
            "--overwrite",
            "--snippet-length", "60",
            "--case-sensitive",
        ]

        # Run the main CLI logic with the fake argv
        main(argv)

        # Check that the results file was created
        assert results_file.exists(), "Results file should be created"
        assert results_file.stat().st_size > 0, "Results file should not be empty"
