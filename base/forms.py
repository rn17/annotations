from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .utils import validate_file, ann_file_validator, LANGUAGE_CHOICES, pairwise_skeleton_files_validator, nlp_file_validator
from django.forms import FileField, ChoiceField, BooleanField


class SecondaryFilesForm(forms.Form):

    MAX_NUM_FILES = 10

    mf = FileField(label='Select main xml file', required=True, validators=[validate_file])

    sf1 = FileField(label='Select secondary xml file 1', validators=[validate_file])
    sf2 = FileField(label='Select secondary xml file 2', validators=[validate_file])
    sf3 = FileField(label='Select secondary xml file 3', validators=[validate_file])
    sf4 = FileField(label='Select secondary xml file 4', validators=[validate_file])
    sf5 = FileField(label='Select secondary xml file 5', validators=[validate_file])
    sf6 = FileField(label='Select secondary xml file 6', validators=[validate_file])
    sf7 = FileField(label='Select secondary xml file 7', validators=[validate_file])
    sf8 = FileField(label='Select secondary xml file 8', validators=[validate_file])
    sf9 = FileField(label='Select secondary xml file 9', validators=[validate_file])
    sf10 = FileField(label='Select secondary xml file 10', validators=[validate_file])

    lang = ChoiceField(choices=LANGUAGE_CHOICES, required=True)

    def clean(self):
        cleaned = super(SecondaryFilesForm, self).clean()

        # different secondary names
        sec_names = set()
        for sec_field_name in self.get_secondary_field_names():
            sec_file_name = self.cleaned_data[sec_field_name].name
            if sec_file_name in sec_names:
                raise forms.ValidationError("Secondary files with same name %s - not allowed" % sec_file_name,
                                            code='invalid')
            else:
                sec_names.add(sec_file_name)
        return cleaned

    def detach_some_fields(self, num):
        if not 1 <= num <= self.MAX_NUM_FILES:
            raise ValidationError("Cannot handle %s files" % num)
        for i in range(num, self.MAX_NUM_FILES):
            self.fields['sf%s' % (i+1)].widget = forms.HiddenInput()
            self.fields['sf%s' % (i+1)].required = False

    def get_secondary_field_names(self):
        return [x.name for x in self.visible_fields() if x.name.startswith('sf')]


class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'is_superuser')


class UploadNlpForm(forms.Form):
    file = FileField(label='select NLP scores file',
                     help_text='file should have the same set of articles as annotation',
                     validators=[nlp_file_validator])


class UploadAnnNlpForm(forms.Form):
    ann_file = FileField(label='select annotation csv file', help_text='',
                         validators=[ann_file_validator])
    nlp_file = FileField(label='select NLP scores file',
                         help_text='both files should have same structure',
                         validators=[nlp_file_validator])

    def clean(self):
        cleaned = super(UploadAnnNlpForm, self).clean()

        cd_ann_file = self.cleaned_data.get('ann_file')
        cd_nlp_file = self.cleaned_data.get('nlp_file')

        if cd_ann_file and cd_nlp_file:
            pairwise_skeleton_files_validator(cd_ann_file, cd_nlp_file)

        return cleaned


class UploadAnnAnnForm(forms.Form):
    ann_file_1 = FileField(label='annotation csv file 1', help_text='',
                           validators=[ann_file_validator])
    ann_file_2 = FileField(label='annotation csv file 2', help_text='both files should have same structure',
                           validators=[ann_file_validator])

    def clean(self):
        cleaned = super(UploadAnnAnnForm, self).clean()

        cd_ann_file_1 = self.cleaned_data.get('ann_file_1')
        cd_ann_file_2 = self.cleaned_data.get('ann_file_2')

        if cd_ann_file_1 and cd_ann_file_2:
            pairwise_skeleton_files_validator(cd_ann_file_1, cd_ann_file_2)

        return cleaned


