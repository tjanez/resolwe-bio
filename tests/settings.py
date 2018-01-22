"""
Django settings for running tests for Resolwe package.

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
from distutils.util import strtobool  # pylint: disable=import-error,no-name-in-module

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'secret'

DEBUG = True

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)


INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',

    'channels',
    'rest_framework',
    'guardian',
    'mathfilters',
    'versionfield',

    'resolwe',
    'resolwe.permissions',
    'resolwe.flow',
    'resolwe.elastic',
    'resolwe.toolkit',
    'resolwe.test_helpers',

    'resolwe_bio',
    'resolwe_bio.kb',
)

ROOT_URLCONF = 'tests.urls'

TEST_RUNNER = 'resolwe.test_helpers.test_runner.ResolweRunner'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

ANONYMOUS_USER_ID = -1

# Check if PostgreSQL settings are set via environment variables
pgname = os.environ.get('RESOLWE_POSTGRESQL_NAME', 'resolwe-bio')
pguser = os.environ.get('RESOLWE_POSTGRESQL_USER', 'resolwe')
pghost = os.environ.get('RESOLWE_POSTGRESQL_HOST', 'localhost')
pgport = int(os.environ.get('RESOLWE_POSTGRESQL_PORT', 55433))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': pgname,
        'USER': pguser,
        'HOST': pghost,
        'PORT': pgport,
    }
}

STATIC_URL = '/static/'

REDIS_CONNECTION = {
    'host': 'localhost',
    'port': int(os.environ.get('RESOLWE_REDIS_PORT', 56380)),
    'db': int(os.environ.get('RESOLWE_REDIS_DATABASE', 0)),
}

FLOW_EXECUTOR = {
    'NAME': 'resolwe.flow.executors.docker',
    # XXX: Change to a stable resolwe image when it will include all the required tools
    'CONTAINER_IMAGE': 'resolwe/bio-linux8-resolwe-preview',
    'CONTAINER_NAME_PREFIX': 'resolwebio',
    'REDIS_CONNECTION': REDIS_CONNECTION,
    'DATA_DIR': os.path.join(PROJECT_ROOT, 'test_data'),
    'UPLOAD_DIR': os.path.join(PROJECT_ROOT, 'test_upload'),
    'RUNTIME_DIR': os.path.join(PROJECT_ROOT, 'test_runtime'),
}
# Set custom executor command if set via environment variable
if 'RESOLWE_DOCKER_COMMAND' in os.environ:
    FLOW_DOCKER_COMMAND = os.environ['RESOLWE_DOCKER_COMMAND']
FLOW_API = {
    'PERMISSIONS': 'resolwe.permissions.permissions',
}
FLOW_EXPRESSION_ENGINES = [
    {
        'ENGINE': 'resolwe.flow.expression_engines.jinja',
        'CUSTOM_FILTERS': [
            'resolwe_bio.expression_filters.sample',
        ]
    },
]
FLOW_EXECUTION_ENGINES = [
    'resolwe.flow.execution_engines.bash',
    'resolwe.flow.execution_engines.workflow',
]

FLOW_MANAGER = {
    'NAME': 'resolwe.flow.managers.workload_connectors.local',
    'REDIS_PREFIX': 'resolwe-bio.manager',
    'REDIS_CONNECTION': REDIS_CONNECTION,
}

FLOW_DOCKER_VOLUME_EXTRA_OPTIONS = {
    'data': 'Z',
    'data_all': 'z',
    'upload': 'z',
    'secrets': 'Z',
    'users': 'Z',
    'tools': 'z',
}

# Don't pull Docker images if set via the environment variable.
FLOW_DOCKER_DONT_PULL = strtobool(os.environ.get('RESOLWE_DOCKER_DONT_PULL', '0'))

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'resolwe.permissions.filters.ResolwePermissionsFilter',
        'rest_framework_filters.backends.DjangoFilterBackend',
    ),
}

FLOW_PROCESSES_FINDERS = (
    'resolwe.flow.finders.FileSystemProcessesFinder',
    'resolwe.flow.finders.AppDirectoriesFinder',
)

FLOW_PROCESSES_DIRS = (os.path.join(PROJECT_ROOT, '../resolwe_bio/tests/'),)

# Do not skip tests that fail on Docker executor if this is set via environment
# variable
if os.environ.get('RESOLWEBIO_TESTS_SKIP_DOCKER_FAILURES', '').lower() in ["no", "false"]:
    TESTS_SKIP_DOCKER_FAILURES = False

# Elastic Search.

ELASTICSEARCH_HOST = os.environ.get('RESOLWE_ES_HOST', 'localhost')
ELASTICSEARCH_PORT = int(os.environ.get('RESOLWE_ES_PORT', '59201'))

# Testing.

TEST_RUNNER = 'resolwe.test_helpers.test_runner.ResolweRunner'
TEST_PROCESS_REQUIRE_TAGS = True
# Don't profile unless set via the environment variable.
TEST_PROCESS_PROFILE = strtobool(os.environ.get('RESOLWE_TEST_PROCESS_PROFILE', '0'))

# Channels.

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'asgi_redis.RedisChannelLayer',
        'ROUTING': 'tests.routing.channel_routing',
        'CONFIG': {
            'hosts': [(REDIS_CONNECTION['host'], REDIS_CONNECTION['port'])],
            'expiry': 3600,
        },
    },
}
