DOMAIN = "tesla_smart_routes"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_PROXY_URL = "proxy_url"
CONF_PROXY_CERT_SHA256 = "proxy_certificate_sha256"

CONF_NAME = "name"
CONF_WAYPOINTS = "waypoints"
CONF_LABEL = "label"
CONF_PLACE_ID = "place_id"
CONF_VIN = "vin"
CONF_VIN_SOURCE = "vin_source"
CONF_VIN_ENTITY = "vin_entity"

DEFAULT_PROXY_URL = "https://localhost:4443"

SUBENTRY_TYPE_ROUTE = "route"

OAUTH2_AUTHORIZE = "https://auth.tesla.com/oauth2/v3/authorize"
OAUTH2_TOKEN = "https://auth.tesla.com/oauth2/v3/token"
OAUTH2_SCOPES = "openid offline_access vehicle_cmds vehicle_device_data"

FLEET_API_BASE = "https://fleet-api.prd.eu.vn.cloud.tesla.com"
WAKE_POLL_INTERVAL = 2    # seconds between state polls
WAKE_TIMEOUT = 120        # seconds before giving up
WAKE_RETRY_INTERVAL = 30  # re-send wake_up if still not online after this many seconds
