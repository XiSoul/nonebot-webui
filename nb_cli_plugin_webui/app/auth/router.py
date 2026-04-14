from fastapi import APIRouter, HTTPException, status
from passlib.exc import UnknownHashError

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.utils.security import jwt, salt

from .exceptions import TokenInvalid
from .schemas import LoginRequest, VerifyRequest
from .utils import ensure_login_token_is_active

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=GenericResponse[str])
async def auth_token(data: LoginRequest) -> GenericResponse[str]:
    """
    - 登录, 成功后返回 JWT 密钥
    """
    try:
        ensure_login_token_is_active()
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))

    try:
        is_valid = salt.verify_token(
            Config.salt.get_secret_value() + data.token,
            Config.hashed_token.get_secret_value(),
        )
    except (ValueError, UnknownHashError):
        raise TokenInvalid()

    if not is_valid:
        raise TokenInvalid()

    secret_key = Config.secret_key.get_secret_value()
    jwt_token = jwt.create_access_for_header(data.mark, secret_key)
    return GenericResponse(detail=jwt_token)


@router.post("/verify", response_model=GenericResponse[str])
async def verify_token(data: VerifyRequest) -> GenericResponse[str]:
    """
    - 验证 JWT 密钥是否可用, 返回到期时间戳
    """
    secret_key = Config.secret_key.get_secret_value()
    try:
        ensure_login_token_is_active()
        jwt_data = jwt.verify_and_read_jwt(data.jwt_token, secret_key)
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))

    parsed_data = dict(jwt_data)

    return GenericResponse(detail=parsed_data["exp"])
