"""SSO / OAuth2 Provider Adapters — Google, Microsoft, Okta.

Each adapter provides:
- authorize_url() → redirect user to provider
- exchange_code(code) → get access token + user info
- Unified user profile format
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


@dataclass
class SSOUser:
    """Unified user profile from SSO provider."""
    provider: str
    provider_user_id: str
    email: str
    name: str
    avatar_url: str = ""
    raw: Dict[str, Any] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.raw is None:
            self.raw = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_user_id": self.provider_user_id,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
        }


class BaseSSOProvider:
    """Base class for SSO providers."""
    PROVIDER_NAME = "base"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def authorize_url(self, state: str = "") -> str:
        raise NotImplementedError

    async def exchange_code(self, code: str) -> SSOUser:
        raise NotImplementedError


class GoogleSSO(BaseSSOProvider):
    PROVIDER_NAME = "google"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def authorize_url(self, state: str = "") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> SSOUser:
        import urllib.request
        import urllib.parse
        import json as _json

        # Exchange authorization code for tokens
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }).encode()
        req = urllib.request.Request(self.TOKEN_URL, data=token_data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tokens = _json.loads(resp.read())
        access_token = tokens["access_token"]

        # Fetch user profile
        req2 = urllib.request.Request(self.USERINFO_URL,
                                      headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            data = _json.loads(resp2.read())
        return self.parse_userinfo(data)

    @staticmethod
    def parse_userinfo(data: Dict[str, Any]) -> SSOUser:
        return SSOUser(
            provider="google",
            provider_user_id=data.get("id", ""),
            email=data.get("email", ""),
            name=data.get("name", ""),
            avatar_url=data.get("picture", ""),
            raw=data,
        )


class MicrosoftSSO(BaseSSOProvider):
    PROVIDER_NAME = "microsoft"
    TENANT = "common"
    AUTH_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
    TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    USERINFO_URL = "https://graph.microsoft.com/v1.0/me"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str,
                 tenant: str = "common") -> None:
        super().__init__(client_id, client_secret, redirect_uri)
        self.tenant = tenant

    def authorize_url(self, state: str = "") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "state": state,
        }
        base = self.AUTH_URL_TEMPLATE.format(tenant=self.tenant)
        return f"{base}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> SSOUser:
        import urllib.request
        import urllib.parse
        import json as _json

        token_url = self.TOKEN_URL_TEMPLATE.format(tenant=self.tenant)
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "scope": "openid email profile User.Read",
        }).encode()
        req = urllib.request.Request(token_url, data=token_data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tokens = _json.loads(resp.read())
        access_token = tokens["access_token"]

        req2 = urllib.request.Request(self.USERINFO_URL,
                                      headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            data = _json.loads(resp2.read())
        return self.parse_userinfo(data)

    @staticmethod
    def parse_userinfo(data: Dict[str, Any]) -> SSOUser:
        return SSOUser(
            provider="microsoft",
            provider_user_id=data.get("id", ""),
            email=data.get("mail", data.get("userPrincipalName", "")),
            name=data.get("displayName", ""),
            raw=data,
        )


class OktaSSO(BaseSSOProvider):
    PROVIDER_NAME = "okta"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str,
                 okta_domain: str = "") -> None:
        super().__init__(client_id, client_secret, redirect_uri)
        self.okta_domain = okta_domain.rstrip("/")

    def authorize_url(self, state: str = "") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        return f"{self.okta_domain}/oauth2/v1/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> SSOUser:
        import urllib.request
        import urllib.parse
        import json as _json

        token_url = f"{self.okta_domain}/oauth2/v1/token"
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }).encode()
        req = urllib.request.Request(token_url, data=token_data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tokens = _json.loads(resp.read())
        access_token = tokens["access_token"]

        userinfo_url = f"{self.okta_domain}/oauth2/v1/userinfo"
        req2 = urllib.request.Request(userinfo_url,
                                      headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            data = _json.loads(resp2.read())
        return self.parse_userinfo(data)

    @staticmethod
    def parse_userinfo(data: Dict[str, Any]) -> SSOUser:
        return SSOUser(
            provider="okta",
            provider_user_id=data.get("sub", ""),
            email=data.get("email", ""),
            name=data.get("name", ""),
            raw=data,
        )


def get_sso_provider(provider: str, **kwargs: Any) -> BaseSSOProvider:
    """Factory for SSO providers."""
    providers = {
        "google": GoogleSSO,
        "microsoft": MicrosoftSSO,
        "okta": OktaSSO,
    }
    cls = providers.get(provider)
    if cls is None:
        raise ValueError(f"Unknown SSO provider: {provider}. Available: {list(providers.keys())}")
    return cls(**kwargs)
