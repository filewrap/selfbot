from selfbot.util import usecs

def test_usecs_zero():
    assert usecs(0) == "0 s"

def test_usecs_seconds():
    assert usecs(1) == "1.00 s"
    assert usecs(1.234) == "1.23 s"
    assert usecs(1.235) == "1.24 s"
    assert usecs(1.239) == "1.24 s"

def test_usecs_milliseconds():
    assert usecs(0.5) == "500.00 ms"
    assert usecs(0.001) == "1.00 ms"
    assert usecs(0.01234) == "12.34 ms"

def test_usecs_microseconds():
    assert usecs(0.0005) == "500.00 µs"
    assert usecs(0.000001) == "1.00 µs"
    assert usecs(0.0001234) == "123.40 µs"
