import hashlib

from app.mta_reverse import MEDIA_XOR_KEY, MEDIA_XOR_KEY_SHA256, MEDIA_XOR_PERIOD


def test_media_xor_key_integrity():
    assert len(MEDIA_XOR_KEY) == 984
    assert MEDIA_XOR_PERIOD == 984
    assert hashlib.sha256(MEDIA_XOR_KEY).hexdigest() == MEDIA_XOR_KEY_SHA256
    assert MEDIA_XOR_KEY_SHA256 == "bcb30443707bdc8b651c1a58aa4152438ce5a6632cc98b294501eb08adbb3547"


def test_media_xor_is_symmetric_and_continuous():
    plain = (b"\x1f\x43\xb6\x75" + bytes(range(256))) * 20
    encrypted = bytes(value ^ MEDIA_XOR_KEY[i % MEDIA_XOR_PERIOD] for i, value in enumerate(plain))
    restored = bytes(value ^ MEDIA_XOR_KEY[i % MEDIA_XOR_PERIOD] for i, value in enumerate(encrypted))
    assert restored == plain
    assert encrypted[MEDIA_XOR_PERIOD] == plain[MEDIA_XOR_PERIOD] ^ MEDIA_XOR_KEY[0]
