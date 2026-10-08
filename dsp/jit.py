"""Opcjonalna kompilacja numba; bez niej moduły używają wektorowych zamienników."""

from __future__ import annotations

import os

HAVE_NUMBA = False
if os.environ.get("ROOTS_NO_NUMBA") != "1":
    try:
        from numba import njit  # type: ignore

        HAVE_NUMBA = True
    except Exception:  # numba nie jest wymagana
        HAVE_NUMBA = False

if not HAVE_NUMBA:

    def njit(*args, **kwargs):  # type: ignore
        if args and callable(args[0]):
            return args[0]

        def wrap(fn):
            return fn

        return wrap
