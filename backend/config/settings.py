from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    ROUTING_PROVIDER=(str, "osrm"),
    ORS_API_KEY=(str, ""),
    OSRM_BASE_URL=(str, "https://router.project-osrm.org"),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-secret-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


INSTALLED_APPS = [
    "trips",
    "corsheaders",
    "rest_framework",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]


ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {}


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}


CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")


USE_TZ = True
TIME_ZONE = "UTC"


#Third party providers that will be used for example for routing I will be using OSRM as it is opoen source and covers what I need.

ROUTING_PROVIDER = env("ROUTING_PROVIDER")
OSRM_BASE_URL = env("OSRM_BASE_URL").rstrip("/")
# openrouteservice token, used for geocoding, initially I was planning to use ORS for routing aswell but it had some linmitations
# so I switched to OSRM for routing and ORS for geocoding. The token is still needed for geocoding.
ORS_API_KEY = env("ORS_API_KEY")