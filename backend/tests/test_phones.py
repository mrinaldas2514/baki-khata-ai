import pytest

from app.services.phones import normalize_mobile


@pytest.mark.parametrize(
    ("text", "normalized"),
    [
        # Bangladesh
        ("01711000001", "+8801711000001"),
        ("01711-000001", "+8801711000001"),
        ("017 1100 0001", "+8801711000001"),
        ("+880 1711-000001", "+8801711000001"),
        ("+8801711000001", "+8801711000001"),
        ("8801711000001", "+8801711000001"),
        ("008801711000001", "+8801711000001"),
        ("01311000001", "+8801311000001"),
        ("01911000001", "+8801911000001"),
        # India
        ("+91 98765 43210", "+919876543210"),
        ("+91-6123456789", "+916123456789"),
        ("919876543210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("98765 43210", "+919876543210"),
        ("0091 9876543210", "+919876543210"),
    ],
)
def test_valid_numbers_are_normalized(text, normalized):
    assert normalize_mobile(text) == normalized


@pytest.mark.parametrize(
    "text",
    [
        "",
        "12345",
        "01211000001",  # no such BD operator (012)
        "0171100000",  # one digit short
        "017110000012",  # one digit long
        "+8801211000001",
        "+915123456789",  # Indian mobiles start with 6-9
        "+44 7700 900123",  # another country
        "+1 202 555 0100",
        "call me",
        "01711o00001",
    ],
)
def test_invalid_numbers_are_rejected(text):
    with pytest.raises(ValueError, match="Bangladesh mobile number"):
        normalize_mobile(text)
