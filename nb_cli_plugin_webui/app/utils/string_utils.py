import re
import random
import secrets
import string

from nb_cli_plugin_webui.i18n import _


class TokenComplexityError(Exception):
    """token complexity error."""


ACCESS_TOKEN_SPECIALS = "!@#$%^&*()-_=+"


def filling_str(text: str, target_length: int) -> str:
    return text + str().join([" " for _ in range(0, target_length - len(text))])


def generate_complexity_string(
    length: int = random.randint(12, 18),
    *,
    use_digits: bool = False,
    use_punctuation: bool = False
) -> str:
    return str().join(
        random.choices(
            string.ascii_letters
            + (string.digits if use_digits else str())
            + (string.punctuation.replace('"', "'") if use_punctuation else str()),
            k=length,
        )
    )


def check_string_complexity(token: str) -> None:
    if len(token) < 10:
        raise TokenComplexityError(_("Token should be at least 10 characters long."))

    if not re.search(r"\d", token):
        raise TokenComplexityError(_("Token should contain at least one digit."))
    if not re.search(r"[a-z]", token):
        raise TokenComplexityError(
            _("Token should contain at least one lowercase letter.")
        )
    if not re.search(r"[A-Z]", token):
        raise TokenComplexityError(
            _("Token should contain at least one uppercase letter.")
        )
    if not re.search(r"[ !@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", token):
        raise TokenComplexityError(
            _("Token should contain at least one special character.")
        )


def generate_access_token(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + ACCESS_TOKEN_SPECIALS

    while True:
        token = str().join(secrets.choice(alphabet) for _ in range(length))
        try:
            check_string_complexity(token)
        except TokenComplexityError:
            continue
        return token


def decode_parse(data: bytes) -> str:
    encodings = ["utf-8", "gbk"]
    decoded_data = str(data)
    for encoding in encodings:
        try:
            decoded_data = data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return decoded_data
