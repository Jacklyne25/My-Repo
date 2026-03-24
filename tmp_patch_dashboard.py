path = 'templates/scheduling/dashboard.html'
with open(path, encoding='utf-8') as f:
    content = f.read()

# Find the back link div and insert the timetable management sector after it
target = '</div>\n{% endblock %}'
insertion = '''
    <!-- Quick Link: Manage All Timetables -->
    <div style="margin-top: 2rem; border-top: 1px solid var(--border); padding-top: 2rem; text-align: center;">
        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 0.75rem;">
            <i class="fas fa-history me-1"></i> Need to view or delete a previous timetable?
        </p>
        <a href="{% url 'scheduling:timetable_list' %}"
           class="btn btn-outline-primary btn-sm px-4"
           style="border-radius: 10px;">
            <i class="fas fa-calendar-alt me-1"></i> Manage Saved Timetables
        </a>
    </div>

</div>
{% endblock %}'''

if target in content:
    new_content = content[:content.rfind(target)] + insertion
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Done.')
else:
    print('Target not found. Last 200 chars:')
    print(repr(content[-200:]))
