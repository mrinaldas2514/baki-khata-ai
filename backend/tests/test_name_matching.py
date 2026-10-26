from dataclasses import dataclass

import pytest

from app.services.name_matching import MatchStatus, clean_name, match_name, name_words


@dataclass
class Person:
    name: str


def names(*names: str) -> list[Person]:
    return [Person(n) for n in names]


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("Rahim bhai", ["rahim"]),
        ("salma apa", ["salma"]),
        ("babu da", ["babu"]),
        ("ruma di", ["ruma"]),
        ("jasim kaka", ["jasim"]),
        ("selim mama", ["selim"]),
        ("rahimbhai", ["rahim"]),
        ("Mr. Hasan", ["hasan"]),
        ("রহিম ভাই", ["রহিম"]),
        ("আয়েশা আপা", ["আয়েশা"]),
        ("Mama", ["mama"]),  # nothing but an honorific: keep it, it may really be the name
    ],
)
def test_honorifics_are_stripped(spoken, expected):
    assert name_words(spoken) == expected


def test_clean_name():
    assert clean_name("salma apa") == "Salma"
    assert clean_name("rahim BHAI") == "Rahim"
    assert clean_name("রহিম ভাই") == "রহিম"


@pytest.mark.parametrize("spoken", ["Rahim", "rahim", "Rahim bhai", "RAHIM VAI", "রহিম", "রহিম ভাই"])
def test_exact_match_ignores_case_honorifics_and_script(spoken):
    customers = names("Karim", "Rahim", "Salma")
    result = match_name(spoken, customers)
    assert result.status == MatchStatus.EXACT
    assert result.match.name == "Rahim"
    assert result.candidates[0] == (result.match, 100)


@pytest.mark.parametrize(
    ("spoken", "customer"),
    [
        ("Rohim", "Rahim"),
        ("Korim", "Karim"),
        ("Kareem", "Karim"),
        ("Shalma", "Salma"),
        ("zakir", "Jakir"),
        ("Rohim bhai", "Rahim"),
        ("করিম", "Korim"),
    ],
)
def test_spelling_variants_match_the_closest_customer(spoken, customer):
    customers = names("Babul", "Selim", customer)
    result = match_name(spoken, customers)
    assert result.status == MatchStatus.FUZZY
    assert result.match.name == customer


@pytest.mark.parametrize("spoken", ["salma", "Salma apa", "সালমা আপা"])
def test_first_name_matches_full_name(spoken):
    result = match_name(spoken, names("Salma Begum", "Rahim"))
    assert result.status == MatchStatus.FUZZY
    assert result.match.name == "Salma Begum"


def test_same_name_twice_is_ambiguous():
    customers = names("Rahim", "Rahim", "Karim")
    result = match_name("rahim bhai", customers)
    assert result.status == MatchStatus.AMBIGUOUS
    assert result.match is None
    assert [c.name for c, _ in result.candidates][:2] == ["Rahim", "Rahim"]


def test_two_equally_close_customers_are_ambiguous():
    result = match_name("rahim", names("Rahim Uddin", "Abdur Rahim"))
    assert result.status == MatchStatus.AMBIGUOUS
    assert {c.name for c, _ in result.candidates} == {"Rahim Uddin", "Abdur Rahim"}


def test_similar_but_different_name_is_only_a_candidate():
    # Rahima is probably a different person from Rahim: offer her, don't pick her.
    result = match_name("Rahim", names("Rahima", "Babul"))
    assert result.status == MatchStatus.AMBIGUOUS
    assert [c.name for c, _ in result.candidates] == ["Rahima"]


def test_different_first_sound_is_a_different_person():
    result = match_name("Rahim", names("Karim"))
    assert result.status == MatchStatus.NEW
    assert result.candidates == []


def test_unknown_name_is_new():
    assert match_name("Selim", names("Rahim", "Salma Begum")).status == MatchStatus.NEW
    assert match_name("Selim", []).status == MatchStatus.NEW


def test_exact_match_beats_close_ones():
    result = match_name("Rahim", names("Rahima", "Rahim", "Abdur Rahim"))
    assert result.status == MatchStatus.EXACT
    assert result.match.name == "Rahim"
    assert [c.name for c, _ in result.candidates] == ["Rahim", "Abdur Rahim", "Rahima"]
