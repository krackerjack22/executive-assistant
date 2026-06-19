"""Tests for lib/address_resolver.py — all 5 formats + subject detection."""

import pytest
from lib import address_resolver as ar
from lib import profile_loader as pl

_SAMPLE_ADDR = {
    "street_1": "5910 Rockwood Ct",
    "street_2": None,
    "city": "Lake Oswego",
    "state_code": "OR",
    "postal_code": "97035",
    "country": "US",
}


def test_street_only():
    assert ar.render(_SAMPLE_ADDR, "street_only") == "5910 Rockwood Ct"


def test_city_st_zip_comma():
    assert ar.render(_SAMPLE_ADDR, "city_st_zip_comma") == "Lake Oswego, OR 97035"


def test_city_st_zip_nocomma():
    assert ar.render(_SAMPLE_ADDR, "city_st_zip_nocomma") == "Lake Oswego OR 97035"


def test_single_line():
    assert ar.render(_SAMPLE_ADDR, "single_line") == "5910 Rockwood Ct, Lake Oswego, OR 97035"


def test_parts_separated():
    result = ar.render(_SAMPLE_ADDR, "parts_separated")
    assert isinstance(result, dict)
    assert result["street"] == "5910 Rockwood Ct"
    assert result["city"] == "Lake Oswego"
    assert result["state"] == "OR"
    assert result["zip"] == "97035"


def test_invalid_format_raises():
    with pytest.raises(ValueError, match="Unknown format"):
        ar.render(_SAMPLE_ADDR, "bad_format")


def test_street_with_street2():
    addr = {**_SAMPLE_ADDR, "street_2": "Suite 100"}
    assert ar.render(addr, "street_only") == "5910 Rockwood Ct Suite 100"


def _index():
    return pl.load_index()


def test_is_subject_address_home():
    assert ar.is_subject_address("Home Address", _index()) is True


def test_is_subject_address_patient():
    assert ar.is_subject_address("Patient Address", _index()) is True


def test_is_subject_address_billing():
    assert ar.is_subject_address("Billing Address", _index()) is True


def test_is_not_subject_physician():
    assert ar.is_subject_address("Physician Address", _index()) is False


def test_is_not_subject_school():
    assert ar.is_subject_address("School Address", _index()) is False


def test_is_not_subject_pharmacy():
    assert ar.is_subject_address("Pharmacy Address", _index()) is False


def test_is_not_subject_employer_office():
    assert ar.is_subject_address("Provider Office Address", _index()) is False
