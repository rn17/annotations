# from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import os
from annotations.settings import MEDIA_ROOT

from base.models import Annotation, AScores, Task
from base.utils import kappa_calc, jaccard_sim
from .utils import parse_annotation_file
import shutil


@receiver(post_save, sender=Annotation)
def save_annotation(sender, instance, **kwargs):

    # Called twice - on created and on saved
    if 'created' in kwargs:
        if kwargs['created']:
            return

    assert isinstance(instance, Annotation)
    instance.calculate_and_save_scores()


@receiver(post_delete, sender=Task)
def delete_task_folder(sender, instance, **kwargs):
    print("INSIDE OF DEL")

    assert isinstance(instance, Task)
    to_del = os.path.join(MEDIA_ROOT, "%s" % instance.id)
    print("Deleting %s ..." % to_del)

    shutil.rmtree(to_del)

    print("Done")

