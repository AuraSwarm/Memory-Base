"""Module tests: memory_base.base."""

from memory_base.base import Base


def test_base_is_declarative_base():
    assert Base is not None
    assert hasattr(Base, "metadata")
    assert hasattr(Base.metadata, "tables")


def test_base_metadata_starts_empty_or_has_models():
    # After importing models, metadata has tables
    from memory_base import models  # noqa: F401
    assert "sessions" in Base.metadata.tables
    assert "messages" in Base.metadata.tables
