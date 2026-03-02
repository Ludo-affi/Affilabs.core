"""
pytest configuration for Affilabs.core test suite.

Registers the @pytest.mark.req("OQ-XXX-NNN") marker used by OQ test suites
to link tests to qualification requirement IDs.
"""
import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "req(req_id): link test to a qualification requirement ID (IQ-xxx or OQ-xxx)",
    )
