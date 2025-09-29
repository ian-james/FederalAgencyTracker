from pathlib import Path
import requests
from urllib.parse import urlparse

def download_pdf(url: str, out_dir: Path, timeout: float = 60.0, overwrite: bool = False, verify_tls: bool = True) -> Path:

    # Ensure output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_url = urlparse(url)
    filename = Path(parsed_url.path).name
    if not filename.lower().endswith(".pdf"):
        raise ValueError("URL does not point to a PDF file.")

    # Create the file path or return it
    out_path = out_dir / filename
    if out_path.exists() and not overwrite:
        print(f"File {out_path} already exists. Skipping download.")
        return out_path

    response = requests.get(url, timeout=timeout, verify=verify_tls)
    response.raise_for_status()

    with open(out_path, "wb") as f:
        f.write(response.content)

    print(f"Downloaded {url} to {out_path}")
    return out_path
