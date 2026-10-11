"""Regression tests for organization-scoped OIDC configuration."""

import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "config.py"


class OIDCOrganizationConfigTests(unittest.TestCase):
    def load_config(self, org_id: str | None) -> dict:
        environment = {
            "OIDC_ISSUER": "https://identity.example.test",
            "OIDC_CLIENT_ID": "test-client",
            "OIDC_REDIRECT_URI": "https://app.example.test/auth/callback",
            "OIDC_POST_LOGOUT_URI": "https://app.example.test/",
            "SESSION_SECRET": "test-session-secret-at-least-32-characters",
        }
        if org_id is not None:
            environment["OIDC_ORG_ID"] = org_id
        with patch.dict(os.environ, environment, clear=True):
            with patch("dotenv.load_dotenv"):
                return runpy.run_path(str(CONFIG_PATH))

    def test_target_organization_scope_is_added_once(self):
        config = self.load_config("123456789")
        self.assertEqual(
            config["OIDC_SCOPES"],
            [
                "openid",
                "profile",
                "email",
                "offline_access",
                "urn:zitadel:iam:org:projects:roles",
                "urn:zitadel:iam:user:resourceowner",
                "urn:zitadel:iam:org:id:123456789",
            ],
        )

    def test_organization_id_is_trimmed(self):
        config = self.load_config(" 123456789 \n")
        self.assertEqual(config["OIDC_ORG_ID"], "123456789")
        self.assertEqual(
            config["OIDC_SCOPES"][-1], "urn:zitadel:iam:org:id:123456789"
        )

    def test_missing_or_empty_organization_id_is_rejected(self):
        for org_id in (None, ""):
            with self.subTest(org_id=org_id):
                with self.assertRaisesRegex(RuntimeError, "OIDC_ORG_ID is required"):
                    self.load_config(org_id)

    def test_whitespace_organization_id_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "OIDC_ORG_ID must not be blank"):
            self.load_config(" \t\n")


if __name__ == "__main__":
    unittest.main()
