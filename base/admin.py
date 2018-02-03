from django.contrib import admin
from .models import Task, Annotation, AScores, Attachment

# Register your models here.
admin.site.register(Task)
admin.site.register(Annotation)
admin.site.register(AScores)
admin.site.register(Attachment)