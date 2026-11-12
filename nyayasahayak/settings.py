"""
Django settings for nyayasahayak project.
NyayaSahayak: AI Legal Aid Assistant
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-nyayasahayak-fallback-secret-key-3289')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

raw_allowed_hosts = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost')
ALLOWED_HOSTS = [h.strip() for h in raw_allowed_hosts.split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local Apps
    'accounts.apps.AccountsConfig',
    'legal_data.apps.LegalDataConfig',
    'assistant.apps.AssistantConfig',
    'notices.apps.NoticesConfig',
    'evaluation.apps.EvaluationConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nyayasahayak.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'nyayasahayak.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Cache for rate limiting
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'nyayasahayak-cache',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'ask'
LOGOUT_REDIRECT_URL = 'home'

# Core Data Paths
DATA_DIR = BASE_DIR / 'data'
ACTS_DIR = DATA_DIR / 'acts'
INDEX_DIR = DATA_DIR / 'index'
REPORTS_DIR = BASE_DIR / 'reports'

# Legal Status & RAG Constants
WAGES_CODE_COMMENCEMENT = "2025-11-21"
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv('DEFAULT_CONFIDENCE_THRESHOLD', '0.35'))
CONFIDENCE_BANDS = {
    "high": 0.60,
    "medium": 0.40,
    "low": 0.35
}
TOP_K = int(os.getenv('TOP_K', '5'))
MAX_QUESTION_LENGTH = int(os.getenv('MAX_QUESTION_LENGTH', '1000'))
ASK_RATE_LIMIT_PER_HOUR = int(os.getenv('ASK_RATE_LIMIT_PER_HOUR', '20'))

# Models & API Settings
EMBEDDING_MODEL_NAME = os.getenv('EMBEDDING_MODEL_NAME', 'paraphrase-multilingual-MiniLM-L12-v2')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')
