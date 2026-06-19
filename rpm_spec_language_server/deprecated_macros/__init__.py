from rpm_spec_language_server.deprecated_macros.altlinux import (
    DEPRECATED_MACROS as ALTLINUX_DEPRECATED_MACROS,
)
from rpm_spec_language_server.deprecated_macros.fedora import (
    DEPRECATED_MACROS as FEDORA_DEPRECATED_MACROS,
)
from rpm_spec_language_server.deprecated_macros.opensuse import (
    DEPRECATED_MACROS as OPENSUSE_DEPRECATED_MACROS,
)

DEPRECATED_MACRO_PROFILES: dict[str, set[str]] = {
    "altlinux": set(ALTLINUX_DEPRECATED_MACROS),
    "fedora": set(FEDORA_DEPRECATED_MACROS),
    "opensuse": set(OPENSUSE_DEPRECATED_MACROS),
}
