"""
User Authentication Models
Handles user authentication, session management, and OAuth integrations
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import Column, String, DateTime, Boolean, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database setup
# Import DATABASE_URL from settings to ensure .env is loaded
try:
    from app.core.config import settings
    DATABASE_URL = settings.database_url
except ImportError:
    # Fallback if settings not available
    DATABASE_URL = "sqlite:///./auth.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """
    User model for authentication
    Stores user credentials and profile information
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)  # Stored in lowercase
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth users

    # OAuth fields
    oauth_provider = Column(String, nullable=True)  # 'google', 'github', or None
    oauth_id = Column(String, nullable=True)  # Unique ID from OAuth provider
    avatar_url = Column(String, nullable=True)

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


# Pydantic models for API

class UserSignupRequest(BaseModel):
    """Request model for user signup"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @validator('email')
    def email_to_lowercase(cls, v):
        """Convert email to lowercase for case-insensitive handling"""
        return v.lower().strip()

    @validator('first_name', 'last_name')
    def clean_names(cls, v):
        """Clean and capitalize names"""
        return v.strip().title()


class UserLoginRequest(BaseModel):
    """Request model for user login"""
    email: EmailStr
    password: str

    @validator('email')
    def email_to_lowercase(cls, v):
        """Convert email to lowercase for case-insensitive handling"""
        return v.lower().strip()


class OAuthLoginRequest(BaseModel):
    """Request model for OAuth login"""
    provider: str = Field(..., pattern="^(google|github)$")
    code: str
    redirect_uri: Optional[str] = None


class UserResponse(BaseModel):
    """Response model for user data"""
    id: int
    email: str
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None
    oauth_provider: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response model for authentication tokens"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


# Database initialization
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
