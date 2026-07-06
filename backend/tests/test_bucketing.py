from app.signal_engine.bucketing import bucket_for


def test_bucket_boundaries():
    assert bucket_for(0.0) == "0-5s"
    assert bucket_for(4.9) == "0-5s"
    assert bucket_for(5.0) == "5-10s"
    assert bucket_for(9.9) == "5-10s"
    assert bucket_for(10.0) == "10-15s"
    assert bucket_for(14.9) == "10-15s"
    assert bucket_for(15.0) == "15s+"
    assert bucket_for(100.0) == "15s+"


def test_bucket_unknown_for_none():
    assert bucket_for(None) == "unknown"
