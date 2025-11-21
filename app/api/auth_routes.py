"""
Authentication API Routes
Handles user login, signup, OAuth, and profile management
"""
from datetime import datetime
import secrets
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from loguru import logger

from app.models.user import (
    User, UserSignupRequest, UserLoginRequest, OAuthLoginRequest,
    UserResponse, TokenResponse, MessageResponse, get_db
)
from app.core.auth import (
    hash_password, verify_password, create_user_token, get_current_user
)
from app.core.oauth import get_oauth_provider

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignupRequest, db: Session = Depends(get_db)):
    """
    User signup endpoint

    Creates a new user account with email and password.
    Email is automatically converted to lowercase for case-insensitive matching.

    Args:
        user_data: User signup request with first_name, last_name, email, password
        db: Database session

    Returns:
        Token response with access token and user data

    Raises:
        HTTP 400: If email already exists
    """
    # Check if user already exists (case-insensitive)
    existing_user = db.query(User).filter(
        User.email == user_data.email.lower()
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        email=user_data.email.lower(),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        hashed_password=hash_password(user_data.password),
        is_active=True,
        is_verified=False,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered: {new_user.email} (ID: {new_user.id})")

    # Generate token
    access_token = create_user_token(new_user.id, new_user.email)

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.from_orm(new_user)
    )


@router.get("/users/count")
async def get_user_count(db: Session = Depends(get_db)):
    """Public endpoint returning total number of users."""
    count = db.query(func.count(User.id)).scalar() or 0
    return {"count": count}


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLoginRequest, db: Session = Depends(get_db)):
    """
    User login endpoint

    Authenticates user with email and password.
    Email matching is case-insensitive.

    Args:
        credentials: User login credentials (email, password)
        db: Database session

    Returns:
        Token response with access token and user data

    Raises:
        HTTP 401: If credentials are invalid or user not found
    """
    # Find user by email (case-insensitive)
    user = db.query(User).filter(
        User.email == credentials.email.lower()
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not user.hashed_password or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    logger.info(f"User logged in: {user.email} (ID: {user.id})")

    # Generate token
    access_token = create_user_token(user.id, user.email)

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.from_orm(user)
    )


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: str):
    """
    Get OAuth authorization URL

    Args:
        provider: OAuth provider ('google' or 'github')

    Returns:
        Dictionary with authorization URL

    Raises:
        HTTP 400: If provider is not supported
    """
    oauth_provider = get_oauth_provider(provider)

    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )

    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)

    auth_url = oauth_provider.get_authorization_url(state)

    return {
        "authorization_url": auth_url,
        "state": state
    }


@router.post("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    oauth_data: OAuthLoginRequest,
    db: Session = Depends(get_db)
):
    """
    OAuth callback endpoint

    Handles OAuth provider callback and creates/authenticates user.

    Args:
        provider: OAuth provider ('google' or 'github')
        oauth_data: OAuth callback data (code, redirect_uri)
        db: Database session

    Returns:
        Token response with access token and user data

    Raises:
        HTTP 400: If provider is invalid or OAuth flow fails
    """
    oauth_provider = get_oauth_provider(provider)

    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )

    # Exchange code for token
    token_response = oauth_provider.exchange_code_for_token(
        oauth_data.code,
        oauth_data.redirect_uri
    )

    if not token_response or "access_token" not in token_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code"
        )

    # Get user info from provider
    user_info = oauth_provider.get_user_info(token_response["access_token"])

    if not user_info or not user_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to fetch user information from provider"
        )

    # Check if user exists (case-insensitive email)
    user = db.query(User).filter(
        User.email == user_info["email"].lower()
    ).first()

    if user:
        # Update OAuth info if needed
        if not user.oauth_provider:
            user.oauth_provider = user_info["provider"]
            user.oauth_id = user_info["id"]
            user.avatar_url = user_info.get("avatar_url")

        user.last_login = datetime.utcnow()
        db.commit()

        logger.info(f"User logged in via OAuth: {user.email} (Provider: {provider})")
    else:
        # Create new user
        user = User(
            email=user_info["email"].lower(),
            first_name=user_info.get("first_name", "User"),
            last_name=user_info.get("last_name", ""),
            oauth_provider=user_info["provider"],
            oauth_id=user_info["id"],
            avatar_url=user_info.get("avatar_url"),
            is_active=True,
            is_verified=True,  # OAuth users are pre-verified
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"New user registered via OAuth: {user.email} (Provider: {provider}, ID: {user.id})")

    # Generate token
    access_token = create_user_token(user.id, user.email)

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.from_orm(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user profile

    Args:
        current_user: Current authenticated user from token

    Returns:
        User profile data
    """
    return UserResponse.from_orm(current_user)


@router.get("/users", response_model=List[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """Publicly list all registered users."""

    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.from_orm(user) for user in users]


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """
    User logout endpoint

    Note: Since we're using stateless JWT tokens, actual logout is handled client-side
    by removing the token. This endpoint is provided for logging purposes.

    Args:
        current_user: Current authenticated user

    Returns:
        Success message
    """
    logger.info(f"User logged out: {current_user.email} (ID: {current_user.id})")

    return MessageResponse(
        message="Successfully logged out",
        success=True
    )


@router.get("/health")
async def auth_health_check():
    """
    Authentication service health check

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat()
    }
