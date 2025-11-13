"""
OAuth Integration Utilities
Handles Google and GitHub OAuth authentication flows
"""
import os
import requests
from typing import Dict, Optional
from loguru import logger

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/google/callback")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:3000/auth/github/callback")


class OAuthProvider:
    """Base class for OAuth providers"""

    def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL"""
        raise NotImplementedError

    def exchange_code_for_token(self, code: str, redirect_uri: Optional[str] = None) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        raise NotImplementedError

    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user information from OAuth provider"""
        raise NotImplementedError


class GoogleOAuth(OAuthProvider):
    """Google OAuth integration"""

    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def get_authorization_url(self, state: str) -> str:
        """
        Get Google OAuth authorization URL

        Args:
            state: Random state string for CSRF protection

        Returns:
            Authorization URL string
        """
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.AUTHORIZATION_URL}?{query_string}"

    def exchange_code_for_token(self, code: str, redirect_uri: Optional[str] = None) -> Optional[Dict]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: Redirect URI used in authorization request

        Returns:
            Token response dictionary or None if failed
        """
        try:
            data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri or GOOGLE_REDIRECT_URI
            }

            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Error exchanging Google code for token: {e}")
            return None

    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """
        Get user information from Google

        Args:
            access_token: OAuth access token

        Returns:
            User info dictionary with keys: id, email, given_name, family_name, picture
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(self.USER_INFO_URL, headers=headers)
            response.raise_for_status()

            user_data = response.json()

            return {
                "id": user_data.get("id"),
                "email": user_data.get("email", "").lower(),
                "first_name": user_data.get("given_name", ""),
                "last_name": user_data.get("family_name", ""),
                "avatar_url": user_data.get("picture"),
                "provider": "google"
            }
        except Exception as e:
            logger.error(f"Error fetching Google user info: {e}")
            return None


class GitHubOAuth(OAuthProvider):
    """GitHub OAuth integration"""

    AUTHORIZATION_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_INFO_URL = "https://api.github.com/user"
    USER_EMAIL_URL = "https://api.github.com/user/emails"

    def get_authorization_url(self, state: str) -> str:
        """
        Get GitHub OAuth authorization URL

        Args:
            state: Random state string for CSRF protection

        Returns:
            Authorization URL string
        """
        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": "read:user user:email",
            "state": state
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.AUTHORIZATION_URL}?{query_string}"

    def exchange_code_for_token(self, code: str, redirect_uri: Optional[str] = None) -> Optional[Dict]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: Redirect URI used in authorization request

        Returns:
            Token response dictionary or None if failed
        """
        try:
            data = {
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri or GITHUB_REDIRECT_URI
            }

            headers = {"Accept": "application/json"}
            response = requests.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Error exchanging GitHub code for token: {e}")
            return None

    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """
        Get user information from GitHub

        Args:
            access_token: OAuth access token

        Returns:
            User info dictionary with keys: id, email, login, name, avatar_url
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }

            # Get user profile
            response = requests.get(self.USER_INFO_URL, headers=headers)
            response.raise_for_status()
            user_data = response.json()

            # Get user emails (GitHub user endpoint doesn't always include email)
            email_response = requests.get(self.USER_EMAIL_URL, headers=headers)
            email_response.raise_for_status()
            emails = email_response.json()

            # Find primary email
            primary_email = next(
                (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                user_data.get("email", "")
            )

            # Parse name
            full_name = user_data.get("name", user_data.get("login", ""))
            name_parts = full_name.split(" ", 1)
            first_name = name_parts[0] if name_parts else user_data.get("login", "User")
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            return {
                "id": str(user_data.get("id")),
                "email": primary_email.lower(),
                "first_name": first_name,
                "last_name": last_name,
                "avatar_url": user_data.get("avatar_url"),
                "provider": "github"
            }
        except Exception as e:
            logger.error(f"Error fetching GitHub user info: {e}")
            return None


# Provider instances
google_oauth = GoogleOAuth()
github_oauth = GitHubOAuth()


def get_oauth_provider(provider: str) -> Optional[OAuthProvider]:
    """
    Get OAuth provider instance by name

    Args:
        provider: Provider name ('google' or 'github')

    Returns:
        OAuth provider instance or None
    """
    providers = {
        "google": google_oauth,
        "github": github_oauth
    }
    return providers.get(provider.lower())
