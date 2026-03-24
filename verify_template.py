import os
import django
from django.template import loader

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') # Changed to core.settings based on earlier error
# Wait, the earlier error said core.settings was not found but I saw core/settings.py in some contexts? 
# Let me check the actual settings module. 
# In Step 60, I see dsams/settings.py.
os.environ['DJANGO_SETTINGS_MODULE'] = 'dsams.settings' 

django.setup()

try:
    t = loader.get_template('scheduling/dashboard.html')
    print('SUCCESS: Template loaded successfully')
except Exception as e:
    print(f'FAILURE: {e}')
    import traceback
    traceback.print_exc()
