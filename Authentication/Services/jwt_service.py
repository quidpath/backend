"""
JWT Token Service for QuidPath Backend
Generates and validates JWT tokens for microservices authentication
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

import jwt
from django.conf import settings

from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser


class JWTService:
    """Service for generating and validating JWT tokens"""

    @staticmethod
    def generate_access_token(user: CustomUser) -> str:
        """
        Generate JWT access token with user and corporate data

        Args:
            user: CustomUser instance

        Returns:
            JWT token string
        """
        payload = {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
            "iss": "quidpath-backend",
        }

        # Add corporate data if user is a CorporateUser
        try:
            corporate_user = CorporateUser.objects.get(customuser_ptr_id=user.id)
            payload["corporate_id"] = str(corporate_user.corporate.id)
            payload["corporate_name"] = corporate_user.corporate.name
            payload["role"] = corporate_user.role.name if corporate_user.role else None
        except CorporateUser.DoesNotExist:
            pass

        # Use environment variable for JWT secret in production
        secret_key = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)

        return jwt.encode(payload, secret_key, algorithm="HS256")

    @staticmethod
    def generate_refresh_token(user: CustomUser) -> str:
        """
        Generate JWT refresh token

        Args:
            user: CustomUser instance

        Returns:
            JWT refresh token string
        """
        payload = {
            "user_id": str(user.id),
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow(),
            "iss": "quidpath-backend",
            "type": "refresh",
        }

        secret_key = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)

        return jwt.encode(payload, secret_key, algorithm="HS256")

    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """
        Decode and validate JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None if invalid
        """
        try:
            secret_key = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)

            payload = jwt.decode(
                token, secret_key, algorithms=["HS256"], issuer="quidpath-backend"
            )

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        """
        Generate new access token from refresh token

        Args:
            refresh_token: JWT refresh token string

        Returns:
            New access token or None if invalid
        """
        payload = JWTService.decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            return None

        try:
            user = CustomUser.objects.get(id=payload["user_id"])
            return JWTService.generate_access_token(user)
        except CustomUser.DoesNotExist:
            return None
