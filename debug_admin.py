import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()
from django.contrib import admin
print("REGISTERED_MODELS:", [m.__name__ for m in admin.site._registry.keys()])
