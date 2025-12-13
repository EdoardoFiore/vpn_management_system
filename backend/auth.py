import os
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select
from database import engine
from models import User, UserRole

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_TO_A_VERY_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12 # 12 Hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    with Session(engine) as session:
        user = session.get(User, username)
        if user is None:
            raise credentials_exception
        if not user.is_active:
             raise HTTPException(status_code=400, detail="Inactive user")
        return user

def check_role(required_roles: List[UserRole]):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return user
    return role_checker

async def check_instance_access(request: Request, user: User = Depends(get_current_user)):
    """
    Dependency to check if the user has access to the instance specified in the path.
    Assumes 'instance_id' is a path parameter.
    """
    if user.role in [UserRole.ADMIN, UserRole.PARTNER]:
        return user
    
    if user.role == UserRole.OPERATOR:
        instance_id = request.path_params.get("instance_id")
        if not instance_id:
            return user # Should not happen if used on correct endpoint
            
        with Session(engine) as session:
            # Re-fetch user with relationships if needed, or query link table
            # Since user object from get_current_user might be detached or not eager loaded
            # Let's query the link table directly
            from models import UserInstance
            link = session.get(UserInstance, (user.username, instance_id))
            if link:
                return user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access to this instance is denied for your role."
    )
