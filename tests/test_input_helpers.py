from util.input_helpers import should_exit_from_input


def test_should_exit_from_input():
    assert should_exit_from_input("__EXIT__") is True
    assert should_exit_from_input("/exit") is True
    assert should_exit_from_input("  /exit  ") is True

    assert should_exit_from_input(None) is False
    assert should_exit_from_input("") is False
    assert should_exit_from_input("/quit") is False
    assert should_exit_from_input("exit") is False

