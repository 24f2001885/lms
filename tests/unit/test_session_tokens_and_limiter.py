"""
Unit tests for session_tokens and the rate limiter (P11).
"""

import time

import pytest

from app.security import session_tokens
from app.security.rate_limit import SlidingWindowLimiter

pytestmark = pytest.mark.security


def test_token_parse_rejects_garbage():
    assert session_tokens.parse_token("5:zz") is None
    assert session_tokens.parse_token("abc:0123456789abcdef") is None
    assert session_tokens.parse_token("") is None
    assert session_tokens.parse_token(None) is None


def test_absolute_lifetime_boundaries():
    now = time.time()
    assert session_tokens.absolute_lifetime_exceeded(now - 300, now, 10) is False
    assert session_tokens.absolute_lifetime_exceeded(now - 700, now, 10) is True
    assert session_tokens.absolute_lifetime_exceeded(None, now, 10) is True
    assert session_tokens.absolute_lifetime_exceeded(now + 100, now, 10) is True


def test_limiter_logic():
    limiter = SlidingWindowLimiter(3, 60)
    assert limiter.check("k1")[0] is True
    assert limiter.record_failure("k1") is False
    assert limiter.record_failure("k1") is False
    assert limiter.record_failure("k1") is True
    allowed, retry = limiter.check("k1")
    assert allowed is False
    assert retry > 0
    limiter.reset("k1")
    assert limiter.check("k1")[0] is True
