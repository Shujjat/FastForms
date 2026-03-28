from django.contrib import admin

from .models import Answer, Form, FormCollaborator, Question, Response

admin.site.register(Form)
admin.site.register(Question)
admin.site.register(Response)
admin.site.register(Answer)
admin.site.register(FormCollaborator)
