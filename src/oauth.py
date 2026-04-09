import logging
from urllib.parse import urlparse

from pydantic import AnyHttpUrl
from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider
from fastmcp.server.auth.auth import ClientRegistrationOptions
from fastmcp.server.auth.providers.in_memory import AccessToken

from .config import Config

logger = logging.getLogger(__name__)


class GoogleTasksOAuthProvider(InMemoryOAuthProvider):
    def __init__(self, base_url: str):
        super().__init__(
            base_url=AnyHttpUrl(base_url),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["read", "write"],
            ),
            required_scopes=["read"],
        )

    def get_routes(self, mcp_path: str = "/"):
        routes = super().get_routes(mcp_path)

        issuer_path = urlparse(str(self.issuer_url)).path.rstrip("/")

        # Fix FastMCP RFC 8414 / RFC 9728 bug: add duplicate routes with the
        # issuer path appended so discovery works behind a reverse proxy
        from starlette.routing import Route

        well_known_prefixes = [
            "/.well-known/oauth-authorization-server",
            "/.well-known/oauth-protected-resource",
        ]
        for route in list(routes):
            if route.path in well_known_prefixes:
                routes.append(
                    Route(
                        f"{route.path}{issuer_path}",
                        route.endpoint,
                        methods=route.methods,
                    )
                )

        return routes

    async def verify_token(self, token: str) -> AccessToken:
        # Try OAuth token first
        try:
            return await super().verify_token(token)
        except Exception:
            pass

        # Fall back to legacy static token
        if Config.MCP_SERVER_TOKEN and token == Config.MCP_SERVER_TOKEN:
            logger.info("Authenticated via legacy static token")
            return AccessToken(
                token=token,
                client_id="legacy-static-client",
                scopes=["read", "write"],
            )

        raise ValueError("Invalid token")
