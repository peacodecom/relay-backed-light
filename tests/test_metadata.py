"""Keep localizable UI text and release metadata in sync."""

import json
from pathlib import Path

from PIL import Image

from custom_components.relay_backed_light.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / DOMAIN


def keys(value, prefix=""):
    """Flatten translation leaf paths without comparing translated text."""
    return {
        path
        for key, child in value.items()
        for path in (
            keys(child, f"{prefix}{key}.")
            if isinstance(child, dict)
            else {f"{prefix}{key}"}
        )
    }


def test_translations_have_all_strings():
    strings = json.loads((COMPONENT / "strings.json").read_text())
    for language in ("en", "de"):
        translation = json.loads(
            (COMPONENT / "translations" / f"{language}.json").read_text()
        )
        assert keys(translation) == keys(strings)
    assert json.loads((COMPONENT / "translations/en.json").read_text()) == strings


def test_manifest_and_hacs_metadata():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "helper"
    assert manifest["categories"] == ["helpers", "lighting"]
    assert manifest["iot_class"] == "calculated"
    assert set(manifest["dependencies"]) == {"light", "switch"}
    assert "filename" not in hacs
    assert "zip_release" not in hacs


def test_public_repository_and_maintainer():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    repository = "https://github.com/peacodecom/relay-backed-light"
    assert manifest["documentation"] == repository
    assert manifest["issue_tracker"] == f"{repository}/issues"
    assert manifest["codeowners"] == ["@norman-bauer"]


def test_mit_license_is_shipped_with_the_integration():
    license_text = (ROOT / "LICENSE").read_text().strip()
    assert license_text.startswith("MIT License\n\nCopyright (c) 2026 Norman Bauer")
    assert (COMPONENT / "LICENSE").read_text().strip() == license_text


def test_custom_repository_instructions_for_both_user_interfaces():
    for document in (ROOT / "README.md", ROOT / "docs/README.de.md"):
        text = document.read_text()
        assert "https://github.com/peacodecom/relay-backed-light" in text
        assert "Add from link" in text
        assert "Custom repositories" in text
        assert "2026.11" in text
        assert "2026.10" in text


def test_publisher_and_copyright_holder_are_documented():
    authors = (ROOT / "AUTHORS.md").read_text()
    assert "Norman Bauer" in authors
    assert "https://github.com/norman-bauer" in authors
    assert "https://github.com/peacodecom" in authors
    assert "https://peacode.com" in authors
    assert "registered trademark" in authors


def test_brand_icons_are_transparent_and_have_expected_sizes():
    brand = COMPONENT / "brand"
    for filename, size in (("icon.png", 256), ("icon@2x.png", 512)):
        path = brand / filename
        assert path.is_file()
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.mode in ("RGBA", "LA")
            assert image.size == (size, size)
            assert image.getchannel("A").getextrema()[0] < 255
