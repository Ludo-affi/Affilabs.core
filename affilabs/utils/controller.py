"""Backward-compatibility shim.

All controller classes have moved to affilabs.utils.controllers package.
This module re-exports them so existing imports continue to work unchanged:

    from affilabs.utils.controller import PicoP4SPR  # still works
    from affilabs.utils.controller import PicoP4PRO  # still works
"""
from affilabs.utils.controllers import (  # noqa: F401
    CH_DICT,
    ControllerBase,
    FlowController,
    KineticController,
    PicoEZSPR,
    PicoKNX2,
    PicoP4PRO,
    PicoP4SPR,
    StaticController,
    ValveCycleMixin,
)
