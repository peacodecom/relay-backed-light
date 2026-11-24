"""Constants for Relay-backed Light."""

DOMAIN = "relay_backed_light"

CONF_RELAY = "relay_entity"
CONF_LIGHT = "light_entity"
CONF_BOOT_DELAY = "boot_delay"
CONF_RELAY_TIMEOUT = "relay_timeout"
CONF_LIGHT_TIMEOUT = "light_timeout"
CONF_RETRY_COUNT = "retry_count"
CONF_RETRY_INTERVAL = "retry_interval"

DEFAULT_OPTIONS = {
    CONF_BOOT_DELAY: 2.0,
    CONF_RELAY_TIMEOUT: 5.0,
    CONF_LIGHT_TIMEOUT: 20.0,
    CONF_RETRY_COUNT: 3,
    CONF_RETRY_INTERVAL: 2.0,
}
