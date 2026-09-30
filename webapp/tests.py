import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from webapp.views import web_static_version


class WebStaticVersionTests(SimpleTestCase):
    def create_assets(self, base_dir):
        static_dir = base_dir / "webapp/static/webapp"
        template_dir = base_dir / "webapp/templates/webapp"
        static_dir.mkdir(parents=True)
        template_dir.mkdir(parents=True)
        (static_dir / "app.js").write_text("console.log('one');")
        (static_dir / "styles.css").write_text("body { color: black; }")
        (static_dir / "mainlogo.jpeg").write_bytes(b"logo-one")
        (template_dir / "index.html").write_text("<main>Room booking</main>")
        return static_dir

    def test_version_is_stable_for_unchanged_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            self.create_assets(base_dir)
            with override_settings(BASE_DIR=base_dir), patch.dict(
                os.environ, {"ROOM_BOOKING_STATIC_VERSION": "release-1"}
            ):
                self.assertEqual(web_static_version(), web_static_version())

    def test_asset_change_invalidates_fixed_release_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            static_dir = self.create_assets(base_dir)
            with override_settings(BASE_DIR=base_dir), patch.dict(
                os.environ, {"ROOM_BOOKING_STATIC_VERSION": "release-1"}
            ):
                original_version = web_static_version()
                (static_dir / "app.js").write_text("console.log('two');")
                self.assertNotEqual(original_version, web_static_version())

    def test_non_javascript_asset_change_invalidates_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            static_dir = self.create_assets(base_dir)
            with override_settings(BASE_DIR=base_dir), patch.dict(
                os.environ, {"ROOM_BOOKING_STATIC_VERSION": ""}
            ):
                original_version = web_static_version()
                (static_dir / "mainlogo.jpeg").write_bytes(b"logo-two")
                self.assertNotEqual(original_version, web_static_version())
