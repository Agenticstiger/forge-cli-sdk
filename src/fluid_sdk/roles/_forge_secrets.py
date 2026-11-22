"""Secret rules vendored from forge-cli, so the SDK can refuse what forge-cli refuses.

Source: ``fluid_build/observability/secret_redactor.py`` and
``fluid_build/alerts/routes.py::secret_option_key`` of forge-cli at commit 83569c0d (the branch
of forge-cli PR 1063, which lands in forge-cli 0.38.0), with the regular expressions kept as
they are there. ``_SENSITIVE_KEY_NAMES`` exists from that commit on.

forge-cli is the authority. Its redactor carries more rules (a registry of known secret
values, JOSE-header detection for a glued JWT, and the like) that a zero-dependency SDK cannot
vendor, so a value or key that passes here can still be refused by forge-cli; the reverse
should not happen. Update this file together with the forge-cli rules it copies.
"""

from __future__ import annotations

import re

_CREDENTIAL_KEY_WORDS = (
    r"api[_-]?key|authorization|aws_secret_access_key|secret[_.-]access[_.-]key|secret[_.-]key|"
    r"client_secret|credentials?|oauth[_-]?token|password|passphrase|"
    r"private[_-]?key(?:_passphrase)?|session[_-]token|secret|token|"
    r"routing[_-]?key|integration[_-]?key|genie[_-]?key|"
    r"passwd|signing[_-]?key|hmac[_-]?key"
)


_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "auth_token",
    "authorization",
    "aws_access_key",
    "aws_secret_key",
    "azure_sas_token",
    "bearer",
    "client_secret",
    "conn_str",
    "connection_string",
    "connection_url",
    "credential",
    "hmac_key",
    "hmackey",
    "genie_key",
    "geniekey",
    "integration_key",
    "integrationkey",
    "jaas",
    "jwt",
    "oauth_token",
    "passwd",
    "password",
    "passphrase",
    "private_key",
    "routing_key",
    "routingkey",
    "secret",
    "session_token",
    "signing_key",
    "signingkey",
    "token",
)

_SENSITIVE_KEY_NAMES = frozenset({"key", "pwd", "sig"})

_JWT_ANCHORED_RE = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+"
    r"(?:\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)?"
)

_JWT_TWO_SEGMENT_RE = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_BEARER_RE = re.compile(r"(?i)\b(Bearer\s+)([^\s,;]+)")
_STRIPE_KEY_RE = re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}")
_GITHUB_TOKEN_RE = re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{20,}")

_PROVIDER_KEY_RES = (
    re.compile(r"\bsk-ant-[A-Za-z0-9-]{30,}"),  # Anthropic
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),  # OpenAI (incl. sk-proj-/sk-svcacct-/sk-admin-)
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}"),  # Slack token
    re.compile(
        r"(?i)\bhttps?://hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9/_-]{8,256}"
    ),
    re.compile(
        r"(?i)\bhttps?://(?:events\.zenduty\.com/integration|(?:www\.)?zenduty\.com/api/events)"
        r"/[A-Za-z0-9/_-]{8,256}"
    ),
    re.compile(
        r"(?i)\bhttps?://events(?:\.eu)?\.pagerduty\.com/(?:x-ere|integration)/[A-Za-z0-9/_-]{8,256}"
    ),
    re.compile(r"(?i)\bGenieKey\s{1,8}[A-Za-z0-9-]{20,128}"),
    re.compile(
        r"(?i)\bhttps?://[a-z0-9.\-]{1,100}\.webhook\.office(?:365)?\.com/[A-Za-z0-9/_@.\-]{8,512}"
    ),
    re.compile(r"(?i)\bhttps?://outlook\.office(?:365)?\.com/webhook/[A-Za-z0-9/_@.\-]{8,512}"),
    re.compile(
        r"(?i)\bhttps?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api(?:/v\d{1,2})?/webhooks/"
        r"\d{5,25}/[A-Za-z0-9_\-]{20,128}"
    ),
    re.compile(r"(?i)(?<=[?&]sig=)[A-Za-z0-9%_\-]{16,256}"),
    re.compile(
        r"(?i)\bAWS4-HMAC-SHA256\s{1,8}Credential=[^\s,'\"]{1,256}"
        r"(?:,\s{0,8}SignedHeaders=[^\s,'\"]{1,512})?(?:,\s{0,8}Signature=[0-9a-f]{16,128})?"
    ),
    re.compile(r"\bhf_[A-Za-z0-9]{30,}"),  # HuggingFace
    re.compile(r"\br8_[A-Za-z0-9]{30,}"),  # Replicate
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"),  # GitLab PAT
    re.compile(r"\bvc_[A-Za-z0-9]{20,}"),  # Vercel
    re.compile(r"\btvly-[A-Za-z0-9_-]{16,}"),  # Tavily (incl. tvly-dev-…) search key
    re.compile(r"\bBSA[A-Za-z0-9_-]{20,}"),  # Brave Search subscription token
    re.compile(r"dapi[a-fA-F0-9]{32}(?:-\d)?"),
)

_URL_USERINFO_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9+.\-]{0,40}://[^/?#@:\s]{0,256}:)(?!\*{3}@)[^/?#@\s]{1,4096}(@)"
)

_URL_TOKEN_USERINFO_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9+.\-]{0,40}://)"
    r"(?=[A-Za-z0-9_.~%\-]{0,256}\d)(?=[A-Za-z0-9_.~%\-]{0,256}[A-Za-z])"
    r"[A-Za-z0-9_.~%\-]{16,256}(@)"
)

_PEM_PRIVATE_KEY_RE = re.compile(
    r"(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----"
)

_ASSIGNMENT_RE = re.compile(
    r"(?ix)"
    r"(?P<key>\b(?:[A-Za-z0-9_]{,128}_)?(?:" + _CREDENTIAL_KEY_WORDS + r")\b)"
    r"(?P<sep>['\"]?\s{,8}[:=]\s{,8})"
    r"(?P<quote>['\"]?)"
    r"(?P<value>.{,256}?)(?P=quote)"
    r"(?=(?:[\s,;}\]]|$))"
)


def looks_like_secret(text: str) -> bool:
    """Whether forge-cli's redactor would (as far as the vendored rules go) mask part of ``text``.

    Covers provider key prefixes (AWS, OpenAI, Anthropic, GitHub, Slack, Google and more),
    Bearer values, JWTs that start ``eyJ``, PEM private keys, URL user info that holds a
    password or a token, a ``key=value`` whose key names a credential, and the incident and chat
    webhook URL shapes. A conservative subset: forge-cli may refuse more.
    """
    for pattern in (
        _STRIPE_KEY_RE,
        _GITHUB_TOKEN_RE,
        *_PROVIDER_KEY_RES,
        _JWT_ANCHORED_RE,
        _JWT_TWO_SEGMENT_RE,
        _BEARER_RE,
        _URL_USERINFO_RE,
        _URL_TOKEN_USERINFO_RE,
        _PEM_PRIVATE_KEY_RE,
        _ASSIGNMENT_RE,
    ):
        if pattern.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Option keys: forge-cli's ``secret_option_key``
# ---------------------------------------------------------------------------

#: A key is read as words: a ``_``, ``-``, ``.``, a change of case (``signingKey``) or a digit
#: after a letter (``password2``) ends one.
_KEY_WORDS = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])")
#: Names of a credential that the redactor's parts do not spell as one word.
_SECRET_WORDS = frozenset(
    {"credentials", "secrets", "passwords", "passphrases", "oauth", "secretkey", "accesskey"}
    | {"secretaccesskey"}
)
#: A word that ends or starts with one of these is a credential's, unless it is one of
#: :data:`_NOT_SECRET_WORDS`.
_SECRET_ENDINGS = ("secret", "token", "password", "passwd", "passphrase", "apikey", "credential")
#: Ordinary words that start with a credential's name: ``tokens`` (``max_tokens``) counts a
#: quantity.
_NOT_SECRET_WORDS = frozenset(
    {"tokens", "tokenize", "tokenized", "tokenizer", "tokenizers", "tokenization"}
    | {"secretary", "secretaries", "secretariat"}
)


def secret_option_key(key: str) -> bool:
    """Whether an option key names a credential (forge-cli's rule, by whole words)."""
    if re.sub(r"[^a-z0-9]", "", key.lower()) in _SENSITIVE_KEY_NAMES:
        return True
    known = {re.sub(r"[^a-z0-9]", "", part) for part in _SENSITIVE_KEY_PARTS} | _SECRET_WORDS
    words = [word.lower() for word in _KEY_WORDS.split(key) if word]
    for start in range(len(words)):
        joined = ""
        for word in words[
            start : start + 3
        ]:  # ``api`` + ``key``, ``secret`` + ``access`` + ``key``
            joined += word
            if joined in known:
                return True
    return any(
        word.endswith(_SECRET_ENDINGS)
        or (word.startswith(_SECRET_ENDINGS) and word not in _NOT_SECRET_WORDS)
        for word in words
    )
