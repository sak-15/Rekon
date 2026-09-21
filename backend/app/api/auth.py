from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.models.organisation import Organisation, User, UserRole
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    OrganisationResponse,
    AuthMeResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Tenancy"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new SaaS Organisation & Admin User",
    description="Provisions a new tenant organisation and an initial admin user. Returns a scoped JWT token.",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    # 1. Check if organisation slug is already claimed
    existing_org = db.query(Organisation).filter(Organisation.slug == payload.org_slug.lower()).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organisation slug '{payload.org_slug}' is already taken. Please choose another slug.",
        )

    # 2. Check if email is already registered across any organisation
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # 3. Create Tenant Organisation
    org = Organisation(
        name=payload.org_name.strip(),
        slug=payload.org_slug.lower().strip(),
        currency=payload.currency.upper().strip(),
    )
    db.add(org)
    db.flush()  # Populates org.id

    # 4. Hash password and create initial Admin User
    user = User(
        org_id=org.id,
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip() if payload.full_name else None,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    # 5. Generate tenant-scoped JWT access token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "org_id": org.id,
            "email": user.email,
            "role": user.role.value,
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user),
        organisation=OrganisationResponse.model_validate(org),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and return JWT",
    description="Validates email and password, returning a JWT scoped to the user's organisation.",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    # 1. Fetch user by email
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Verify account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact your organization administrator.",
        )

    # 3. Issue scoped JWT token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "org_id": user.org_id,
            "email": user.email,
            "role": user.role.value,
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user),
        organisation=OrganisationResponse.model_validate(user.organisation),
    )


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Get current user and organisation",
    description="Returns the profile and tenant organisation details of the authenticated caller.",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return AuthMeResponse(
        user=UserResponse.model_validate(current_user),
        organisation=OrganisationResponse.model_validate(current_user.organisation),
    )
