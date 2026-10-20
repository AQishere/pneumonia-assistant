from datetime import timedelta

from api.validation import check_reading, check_taken_at, validate_readings
from tests.conftest import NOW


def test_temperature_10_is_out_of_range():
    assert check_reading("temperature", 10)["code"] == "OUT_OF_RANGE"


def test_temperature_38_is_likely_celsius_with_conversion():
    err = check_reading("temperature", 38)
    assert err["code"] == "LIKELY_CELSIUS"
    assert err["suggested_value"] == 100.4


def test_temperature_38_5_suggests_101_3():
    assert check_reading("temperature", 38.5)["suggested_value"] == 101.3


def test_spo2_above_100_is_out_of_range():
    assert check_reading("spo2", 105)["code"] == "OUT_OF_RANGE"


def test_explicit_celsius_unit_is_rejected_with_suggestion():
    err = check_reading("temperature", 38.5, unit="°C")
    assert err["code"] == "WRONG_UNIT"
    assert err["suggested_value"] == 101.3


def test_wrong_unit_for_other_vitals():
    assert check_reading("sbp", 120, unit="kPa")["code"] == "WRONG_UNIT"


def test_boundaries_are_inclusive_and_valid_values_pass():
    for vital, value in [("heart_rate", 20), ("heart_rate", 250), ("respiratory_rate", 4),
                         ("sbp", 250), ("spo2", 100), ("temperature", 90), ("temperature", 110)]:
        assert check_reading(vital, value) is None, (vital, value)
    assert check_reading("temperature", 101.3, unit="F") is None
    assert check_reading("spo2", 95, unit="%") is None


def test_non_numbers_and_unknown_vitals():
    assert check_reading("heart_rate", float("nan"))["code"] == "NOT_A_NUMBER"
    assert check_reading("heart_rate", True)["code"] == "NOT_A_NUMBER"
    assert check_reading("glucose", 5)["code"] == "UNKNOWN_VITAL"


def test_batch_errors_carry_index():
    errs = validate_readings([{"vital": "spo2", "value": 95},
                              {"vital": "spo2", "value": 105}])
    assert [e["index"] for e in errs] == [1]


def test_future_timestamp():
    assert check_taken_at(NOW + timedelta(hours=1), NOW)["code"] == "FUTURE_TIMESTAMP"
    assert check_taken_at(NOW - timedelta(hours=1), NOW) is None
