"""Keep the tests out of Miso's actual life.

The suites exercise `memory` and `jail`, which write a journal, episodes, a
collection and a compost heap. Pointed at the real `/home` they do exactly what
they are supposed to -- into the diary of the cat you are actually keeping.
That is how lines like "hello from a string" ended up in her memories, sitting
alongside real ones, waiting to be folded into her self-summary by the nightly
dream as though they had happened.

Call `scratch_home()` before touching `jail` or `memory` in any test.
"""
from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

from miso import config


def scratch_home() -> Path:
    """Point /home at a throwaway directory for the rest of this process.

    `jail` reads `config.MOUNTS` on every call rather than caching it, so
    redirecting the entry here is enough -- no monkeypatching of jail itself.
    """
    tmp = Path(tempfile.mkdtemp(prefix="miso-test-"))
    config.HOME_REAL = tmp
    config.MOUNTS["/home"] = tmp
    atexit.register(shutil.rmtree, tmp, True)
    return tmp
