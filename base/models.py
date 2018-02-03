import random

from django.db import models

from base.utils import validate_file, get_filename_tail, EN, LANGUAGE_CHOICES
from django.contrib.auth.models import User
from annotations.settings import TASKS_LIMIT_ACTIVE
from .utils import parse_annotation_file, kappa_calc, jaccard_sim

# Create your models here.


MAIN_XML_FILE_DIR = 'main_file'
SEC_XML_FILE_DIR = 'secondary_files'
ANNOTATIONS_FILE_DIR = 'annotations'


def main_file_path(instance, filename):
    return '%s/%s/%s' % (instance.id, MAIN_XML_FILE_DIR, filename)


def secondary_file_path(instance, filename):
    return '%s/%s/%s' % (instance.task.id, SEC_XML_FILE_DIR, filename)


class Task(models.Model):

    id = models.AutoField(primary_key=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)  # TODO remove
    created = models.DateTimeField(auto_now=False, auto_now_add=True)
    main_xml = models.FileField(upload_to=main_file_path, validators=[validate_file])
    is_third_allowed = models.BooleanField(default=False)

    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default=EN)

    def __str__(self):
        return "Task %s: %s" % (self.id, self.main_filename())

    # configure id first, then save attached xml files
    def save(self, *args, **kwargs):
        if self.pk is None:

            saved_main_xml = self.main_xml
            self.main_xml = None

            super(Task, self).save(*args, **kwargs)
            self.main_xml = saved_main_xml

        super(Task, self).save(*args, **kwargs)

    def main_filename(self):
        return get_filename_tail(self.main_xml)

    def can_accept_new_annotations(self):
        if TASKS_LIMIT_ACTIVE:
            if self.is_third_allowed:
                max_possible = 3
            else:
                max_possible = 2
            return self.annotations.count() < max_possible
        else:
            return True

    # TODO check num of sql-requests
    def associated_usernames(self):
        return [e.annotator.username for e in self.annotations.all()]

    # @register.simple_tag
    def can_accept_user_annotation(self, user):
        # self.objects.filter(annotations__annotator__username=)

        return self.objects.filter(annotations__annotator=user).count() == 0


class Attachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='secondary_xmls')
    file = models.FileField(upload_to=secondary_file_path, validators=[validate_file])

    def sec_filename(self):
        return get_filename_tail(self.file)


def annotation_file_path(instance, filename):
    print("AFP!!!!!!!!!!!", filename)

    cnt = Annotation.objects.filter(task=instance.task).count()
    f_name = "%s_%s_%s.csv" %(instance.task.id, instance.annotator.username, cnt)
    return '%s/%s/%s' % (instance.task.id, ANNOTATIONS_FILE_DIR, f_name)


class Annotation(models.Model):

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='annotations')
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now=False, auto_now_add=True)           # not modifiable
    file = models.FileField(upload_to=annotation_file_path)

    def __str__(self):
        return "Annotation %s (task %s) from %s" % (self.id, self.task_id, self.annotator.username)

    def calculate_and_save_scores(self):
        print("Calculation of scores...")
        for other in Annotation.objects.filter(task_id=self.task.id):
            if other != self:
                other_dict = parse_annotation_file(other.file.path)
                curr_dict = parse_annotation_file(self.file.path)

                kappa = kappa_calc(other_dict, curr_dict)
                j_d = jaccard_sim(other_dict, curr_dict)
                kappa2 = kappa_calc(other_dict, curr_dict, modified=True)

                score_object = AScores.objects.create(task_id=self.task.id, a1=other, a2=self,
                                                      kappa_score=kappa,
                                                      jaccard_score=j_d,
                                                      kappa2_score=kappa2)
                score_object.save()
                print("+Another score!")
        print("Calculation done")


# Let's not create M2M through Score
class AScores(models.Model):

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='scores')
    a1 = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name='rs1')
    a2 = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name='rs2')
    kappa_score = models.FloatField()
    jaccard_score = models.FloatField()
    kappa2_score = models.FloatField()
