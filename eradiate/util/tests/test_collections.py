import pytest

from eradiate.util.collections import ndict
from eradiate.util.units import ureg


def test_ndict_construct():
    # Empty constructor
    cd = ndict()
    assert cd == {}

    # Init from dictionary
    d = {"a": 1, "b": 2}
    cd = ndict(d)
    assert cd == d
    assert cd is not d

    # Check that dict used for initialisation is copied
    d["a"] = 2
    assert cd != d


def test_ndict_update():
    d1 = ndict({"a": 1, "b": [1, 2, 3], "c": {"a": 1}, "d": [1, 2]})
    d2 = ndict({"b": 4, "c": {"b": 2}, "d": [2, 3]})

    # Check that the merge strategy works as intended
    d1.update(d2)
    assert d1 == {"a": 1, "b": 4, "c": {"a": 1, "b": 2}, "d": [2, 3]}
    assert isinstance(d1, ndict)


def test_ndict_rget():
    d = ndict({"a": 1, "b": [1, 2, 3], "c": {"a": 1}, "d": [1, 2]})

    # Get value at existing key
    assert d.rget("c.a") == 1

    # Get item from list
    assert d.rget("d")[0] == 1

    # Raise on missing key (due to wrong item type) and check exception content
    with pytest.raises(KeyError) as e:
        d.rget("a.b.c")
        assert e.args == ("a.b.c",)

    # Raise on missing key (missing from dict keys)
    with pytest.raises(KeyError):
        d.rget("a.w")


def test_ndict_rset():
    d = ndict()

    # Create key at root
    d.rset("a", 1)
    assert d == {"a": 1}

    # Update existing key
    d.rset("a", 2)
    assert d == {"a": 2}

    # Create keys at higher level with missing intermediate key
    d.rset("b.c", "hello world")
    assert d == {"a": 2, "b": {"c": "hello world"}}

    # Raise on inappropriate type
    with pytest.raises(KeyError):
        d = ndict({"a": None})
        d.rset("a.b", 1)
        assert d == {"a": {"b": 1}}
