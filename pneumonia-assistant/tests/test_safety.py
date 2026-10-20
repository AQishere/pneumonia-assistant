from api.safety import alerts, derive_hypoxemia


def test_spo2_84_fires_low_spo2_and_hypoxemia():
    readings = {"spo2": [96, 84, 95]}
    out = alerts(readings)
    assert out == [{"code": "LOW_SPO2", "message": "Blood oxygen (SpO2) dropped to 84% (below 90%)",
                    "value": 84.0}]
    assert derive_hypoxemia(readings, None) == 1


def test_rr_and_sbp_alerts():
    codes = {a["code"] for a in alerts({"respiratory_rate": [22, 34], "sbp": [110, 85]})}
    assert codes == {"HIGH_RESPIRATORY_RATE", "LOW_SBP"}


def test_thresholds_are_strict():
    assert alerts({"spo2": [90], "respiratory_rate": [30], "sbp": [90]}) == []


def test_doctor_flag_sets_hypoxemia():
    assert derive_hypoxemia({"spo2": [97]}, 1) == 1
    assert derive_hypoxemia({"spo2": [97]}, 0) == 0
    assert derive_hypoxemia({}, None) == 0
