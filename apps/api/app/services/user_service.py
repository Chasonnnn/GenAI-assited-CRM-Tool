"""User service - user operations and session management."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import User


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by email (case-insensitive)."""
    return db.query(User).filter(User.email == email.lower()).first()


def revoke_all_sessions(db: Session, user_id: UUID) -> bool:
    """
    Revoke all sessions for a user by bumping token_version.
    
    Existing tokens with old version will fail validation.
    
    Returns:
        True if user found and sessions revoked, False if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    user.token_version += 1
    db.commit()
    return True


def disable_user(db: Session, user_id: UUID) -> bool:
    """
    Disable user account.
    
    Also revokes all sessions by bumping token_version.
    
    Returns:
        True if user found and disabled, False if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    user.is_active = False
    user.token_version += 1  # Also revoke sessions
    db.commit()
    return True


def enable_user(db: Session, user_id: UUID) -> bool:
    """
    Re-enable a disabled user account.
    
    Returns:
        True if user found and enabled, False if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    user.is_active = True
    db.commit()
    return True


def update_user_profile(
    db: Session, 
    user_id: UUID, 
    display_name: str | None = None,
    avatar_url: str | None = None
) -> User | None:
    """
    Update user profile fields.
    
    Only updates fields that are provided (not None).
    
    Returns:
        Updated user or None if not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    if display_name is not None:
        user.display_name = display_name
    if avatar_url is not None:
        user.avatar_url = avatar_url
    
    db.commit()
    db.refresh(user)
    return user
