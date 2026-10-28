import pytest

from app.services.number_words import normalize_numbers, numbers_in


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Banglish number words
        ("salma apa pach sho taka baki", "salma apa 500 taka baki"),
        ("dedh hajar dilo", "1500 dilo"),
        ("arai sho taka", "250 taka"),
        ("sare tin sho", "350"),
        ("poune dui hajar", "1750"),
        ("sowa sho taka baki", "125 taka baki"),
        ("shoa hajar", "1250"),
        ("sowa tin sho taka", "325 taka"),
        ("sowa dui hajar", "2250"),
        ("সোয়া শো টাকা", "125 টাকা"),
        ("ek hajar pach sho ponchash taka", "1550 taka"),
        ("dui hajar taka nilo", "2000 taka nilo"),
        ("hajar taka dilo", "1000 taka dilo"),
        ("bish taka", "20 taka"),
        ("pachsho baki", "500 baki"),
        ("1.5 hajar", "1500"),
        ("2 hajar", "2000"),
        ("5 lakh", "500000"),
        # Bangla script and digits
        ("রহিম ২০০ টাকা দিল", "রহিম 200 টাকা দিল"),
        ("দেড় হাজার টাকার চাল", "1500 টাকার চাল"),
        ("পাঁচশো টাকা বাকি", "500 টাকা বাকি"),
        ("সাড়ে তিন শো", "350"),
        # English
        ("five hundred taka", "500 taka"),
        # Thousands separators
        ("Abul 2,500 tk jama", "Abul 2500 tk jama"),
        ("1,25,000 taka", "125000 taka"),
    ],
)
def test_amounts_become_digits(text, expected):
    assert normalize_numbers(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "rahim bhai 2 kg chal 120 taka baki",  # digits are left as they are
        "paid 500 so total is fine",  # "so" after digits is English, not x100
        "met him at the shop",  # "at" (8) only counts before sho/hajar/taka
        "tin kg alu",  # a quantity, not money
        "dosh",  # a lone number word with no multiplier or currency
    ],
)
def test_ordinary_words_are_untouched(text):
    assert normalize_numbers(text) == text


def test_numbers_in():
    assert numbers_in("polash 1 dozen dim r 2 ta pauruti 180 baki") == {1, 2, 180}
    assert numbers_in("no numbers") == set()
