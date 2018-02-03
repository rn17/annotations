import csv
import statistics
from io import StringIO
from os.path import join, basename
from random import randint
from tempfile import TemporaryFile

from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, FormView

from annotations.settings import MEDIA_ROOT, MEDIA_URL
from base.utils import LBL, EMPTY, LANGUAGE_CHOICES, \
    process_xml, parse_annotation_file_by_descriptor, kappa_calc, jaccard_sim, pairwise_skeleton_files_validator, \
    convert_to_tmp_file, CHART_SPLITS
from .forms import SecondaryFilesForm, CustomUserCreationForm, UploadNlpForm, UploadAnnNlpForm, UploadAnnAnnForm
from .models import Task, Annotation, Attachment, AScores
from .numpy_utils import compare_files

TEMP_STATS = 'temp_stats'


class TaskListView(ListView):
    template_name = 'tasks.html'
    model = Task
    paginate_by = 5

    def get_all(self):
        return Task.objects.all()

    def get_by_lang(self, lang):
        return Task.objects.filter(language=lang)

    def get_queryset(self):

        if 'lang' in self.request.GET.keys():
            r = self.get_by_lang(self.request.GET['lang'])
        else:
            r = self.get_all()
        return r.select_related('creator')\
            .prefetch_related('annotations', 'scores', 'secondary_xmls')\
            .order_by('-created')
            # .select_related('annotations.annotator')\                         TODO !!!!!!!!!!!!!

    def get_context_data(self, *, object_list=None, **kwargs):
        to_return = super(TaskListView, self).get_context_data(object_list=object_list, **kwargs)

        if 'lang' in self.request.GET:
            to_return['lang'] = self.request.GET['lang']

        to_return['langs'] = [l[0] for l in LANGUAGE_CHOICES]

        assert 'page_obj' in to_return, "%s" % to_return

        if self.request.user.is_authenticated:
            has_some_rights = self.request.user.has_perm('base.delete_task')
        else:
            has_some_rights = False
        to_return['manager'] = has_some_rights

        to_return['tlv'] = True

        return to_return


@login_required
def make_annotation(request, a_id):

    task = get_object_or_404(Task, id=a_id)

    if task.annotations.filter(annotator=request.user).count() > 0:
        return HttpResponse('Forbidden: already annotated by me', status=403)

    main_xml = process_xml(task.main_xml.path)
    secondary_xmls = []
    for sec in task.secondary_xmls.all():
        parsed_sec = process_xml(sec.file.path)
        secondary_xmls.append({'sec_name': sec.sec_filename(), 'sec_content': parsed_sec})

    hostport = "http://%s" % request.get_host()

    context = {
        'hostport': hostport,
        'main_xml_content': main_xml,
        'secondary_xmls': secondary_xmls,
        'main_xml_name': task.main_filename(),
        'empty_tag': EMPTY}
    return render(request, 'annotate.html', context)


def metrics_single(request, a_id):
    context = dict()

    if request.method == "POST":
        frm = UploadNlpForm(request.POST, request.FILES)
        if frm.is_valid():
            ann = get_object_or_404(Annotation, id=int(a_id))
            summary_file_suffix = "stats_t%s_%s_%s.csv" % (ann.task.id, ann.annotator.username, ann.id)
            summary_file_path = join(MEDIA_ROOT, TEMP_STATS, summary_file_suffix)

            true_file_desc = open(ann.file.path, mode='rt')
            # pred_file_desc = convert_to_tmp_file(request.FILES['file'])

            cd_pred_file = frm.cleaned_data.get('file')

            try:
                pairwise_skeleton_files_validator(true_file_desc, cd_pred_file)

                f_score = compare_files(true_file_descriptor=true_file_desc,
                                        pred_file_descriptor=cd_pred_file,
                                        output_file_path=summary_file_path)
                # fp = open('/home/antre/PyProjects/upw_annotation_service/annotations/global_static/generated_scores.csv', 'rt')

                context['hostport'] = "http://%s" % request.get_host()
                context['chart_file'] = join(MEDIA_URL, TEMP_STATS, summary_file_suffix)
                context['f_score'] = f_score

            except ValidationError as ve:           # from pairwise comparison
                frm.add_error(None, ve)

    else:
        frm = UploadNlpForm()
    context['file_form'] = frm
    return render(request, 'metrics.html', context=context)


def metrics_own(request):
    context = dict()

    if request.method == "POST":
        frm = UploadAnnNlpForm(request.POST, request.FILES)
        if frm.is_valid():
            summary_file_suffix = "stats_custom_%s.csv" % (randint(1000000, 1999999))
            summary_file_path = join(MEDIA_ROOT, TEMP_STATS, summary_file_suffix)

            true_file_desc = convert_to_tmp_file(request.FILES['ann_file'])
            pred_file_desc = convert_to_tmp_file(request.FILES['nlp_file'])

            f_score = compare_files(true_file_descriptor=true_file_desc,
                                    pred_file_descriptor=pred_file_desc,
                                    output_file_path=summary_file_path)

            context['f_score'] = f_score
            context['hostport'] = "http://%s" % request.get_host()
            context['chart_file'] = join(MEDIA_URL, TEMP_STATS, summary_file_suffix)
    else:
        frm = UploadAnnNlpForm()
    context['file_form'] = frm
    context['ann_nlp'] = True
    return render(request, 'metrics.html', context=context)


def aaa(request):
    from .numpy_utils import top_values
    f = open('/home/antre/PyProjects/upw_annotation_service/LSA500_final_withoutsw_without_stemming.csv', mode='rt')
    top_values(f)


def ann_cmp_2(request):
    context = dict()

    if request.method == "POST":
        frm = UploadAnnAnnForm(request.POST, request.FILES)
        if frm.is_valid():

            ann_file_1_desc = convert_to_tmp_file(request.FILES['ann_file_1'])
            ann_file_2_desc = convert_to_tmp_file(request.FILES['ann_file_2'])

            try:
                other_dict = parse_annotation_file_by_descriptor(ann_file_1_desc)
                curr_dict = parse_annotation_file_by_descriptor(ann_file_2_desc)

                kappa = kappa_calc(other_dict, curr_dict)
                jaccard = jaccard_sim(other_dict, curr_dict)
                kappa2 = kappa_calc(other_dict, curr_dict, modified=True)

                context['kappa'] = kappa
                context['kappa2'] = kappa2
                context['jaccard'] = jaccard
            except Exception as ex:
                frm.add_error(None, ValidationError(str(ex)))

    else:
        frm = UploadAnnAnnForm()
    context['upload_form'] = frm
    context['ann_cmp_2'] = True
    return render(request, 'ann_ann.html', context=context)


def metrics_join(request, a1_id, a2_id, mode):
    assert mode in {'u', 'i'}
    context = dict()

    if request.method == "POST":
        frm = UploadNlpForm(request.POST, request.FILES)
        if frm.is_valid():

            ann1 = get_object_or_404(Annotation, id=int(a1_id))
            ann2 = get_object_or_404(Annotation, id=int(a2_id))
            assert ann1 != ann2, "same annotation chosen"
            assert ann1.task.id == ann2.task.id, "annotations should be selected for the same task"

            summary_file_suffix = "stats_t%s_%s_%s_%s_%s_%s.csv" % (ann1.task.id,
                                                                    ann1.annotator.username, ann1.id,
                                                                    ann2.annotator.username, ann2.id,
                                                                    mode)
            summary_file_path = join(MEDIA_ROOT, TEMP_STATS, summary_file_suffix)

            af1 = open(ann1.file.path, mode='rt')
            af2 = open(ann2.file.path, mode='rt')

            print("JOIN in progress...")
            tf_join = TemporaryFile(mode='w+t')
            for line in af1.readlines():
                elems1 = line.strip().split(',')
                elems2 = af2.readline().strip().split(',')
                assert len(elems1) == len(elems2)
                res_line = []
                for e1, e2 in zip(elems1, elems2):
                    assert e1 == e2 or not (e1 and e2)
                    val = ''
                    if mode == 'u':
                        if e1:
                            val = e1
                        else:
                            val = e2
                    elif mode == 'i':
                        if e1 == e2:
                            val = e1
                    res_line.append(val)
                tf_join.write(','.join(res_line) + '\n')
                print(res_line)
            tf_join.seek(0)
            print("JOIN done")

            pred_file_desc = frm.cleaned_data.get('file')

            try:
                pairwise_skeleton_files_validator(tf_join, pred_file_desc)

                f_score = compare_files(true_file_descriptor=tf_join,
                                        pred_file_descriptor=pred_file_desc,
                                        output_file_path=summary_file_path)

                context['f_score'] = f_score
                context['hostport'] = "http://%s" % request.get_host()
                context['chart_file'] = join(MEDIA_URL, TEMP_STATS, summary_file_suffix)

            except ValidationError as ve:           # from pairwise comparison
                frm.add_error(None, ve)
    else:
        frm = UploadNlpForm()
    context['file_form'] = frm
    return render(request, 'metrics.html', context=context)


# TODO maybe insert login_req inside
@login_required
@csrf_exempt
def submit_annotation(request):

    if request.method == 'POST':

        referer = request.META.get('HTTP_REFERER', '')
        task_id = int(referer.strip().rsplit('/', 2)[1])
        print(" task:", task_id)
        print(request.POST)

        task = get_object_or_404(Task, id=task_id)

        if task.annotations.filter(annotator=request.user).count() > 0:
            return HttpResponse('Forbidden: already annotated by me', status=403)

        main_xml_parsed = process_xml(task.main_xml.path)
        main_xml_keys = [x[LBL] for x in main_xml_parsed if LBL in x]

        sec_xml_keys = list()
        for sec in task.secondary_xmls.all():
            sec_xml_parsed = process_xml(sec.file.path)
            sec_xml_keys.extend(["%s:%s" % (sec.sec_filename(), x[LBL]) for x in sec_xml_parsed if LBL in x])

        if set(main_xml_keys) != set(request.POST.dict().keys()):
            return HttpResponse("Fail on main_keys compare")

        to_write = dict()
        for k in request.POST.dict().keys():
            secondary = request.POST.getlist(k)

            to_write[k] = [''] * len(sec_xml_keys)

            for sec_key in secondary:
                if sec_key == EMPTY:
                    if len(secondary) != 1:
                        raise AssertionError('empty / not empty')
                else:
                    assert sec_key in sec_xml_keys
                    to_write[k][sec_xml_keys.index(sec_key)] = 1

        assert len(to_write) == len(main_xml_keys)

        #with TemporaryFile() as f:
        string_buffer = StringIO()

        # csv_writer = csv.DictWriter(string_buffer, fieldnames=fieldnames, delimiter='\t', quotechar='"')
        # csv_writer.writeheader()
        csv_writer = csv.writer(string_buffer, delimiter=',', quotechar='"')
        header_row = ['Query Index', 'Article']
        header_row.extend(sec_xml_keys)
        csv_writer.writerow(header_row)

        for i, art in enumerate(main_xml_keys):
            row_to_write = [i, art]
            row_to_write.extend(to_write[art])
            csv_writer.writerow(row_to_write)

        content = string_buffer.getvalue()
        a_gen_file = ContentFile(content, name='tmp1.csv')      # !!! if without name => won't ask upload_to !!!

        co = Annotation.objects.create(task_id=task_id, file=a_gen_file, annotator=request.user)
        co.save()
        if co:
            print("success.")
            return HttpResponse("success", content_type="text/plain")       # TODO add status
        else:
            print("not ok")
            return HttpResponse("Fail: annotation was not created")

    else:
        return HttpResponse("Fail")


class CreateTaskView(LoginRequiredMixin, FormView):
    template_name = 'task_add.html'
    form_class = SecondaryFilesForm
    success_url = 'base:add_task'                 # ! add num

    def get(self, request, *args, **kwargs):
        """
        GET...<WSGIRequest: GET '/tasks/add_task'> <=> () <=> {}
        GCD...
        R2R...
        """
        print("GET...%s <=> %s <=> %s" %(request, args, kwargs))
        try:
            return super(CreateTaskView, self).get(request, *args, **kwargs)
        except:
            return HttpResponse('Bad request: num must be in range 1-5', status=400)

    def form_valid(self, form):
        print("FV...")
        return super(CreateTaskView, self).form_valid(form)

    def form_invalid(self, form):
        print("FNV...")
        return super(CreateTaskView, self).form_invalid(form)

    def render_to_response(self, context, **response_kwargs):
        print("R2R...")
        return super(CreateTaskView, self).render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        print("GCD...")
        context = super(CreateTaskView, self).get_context_data(**kwargs)
        context['num'] = self.get_num()
        context['adt'] = True
        context['f_num_list'] = range(1, 1 + SecondaryFilesForm.MAX_NUM_FILES)
        return context

    def get_form(self, form_class=None):
        print("GF...")
        form = super(CreateTaskView, self).get_form(form_class)
        assert isinstance(form, SecondaryFilesForm)
        form.detach_some_fields(self.get_num())
        return form

    def get_num(self):
        assert 'num' in self.request.GET
        return int(self.request.GET['num'])

    def post(self, request, *args, **kwargs):
        """
        <WSGIRequest: POST '/tasks/add_task'>
        >>
        ()
        >> >>
        {}
        GF...
        Validating...
        Validating...
        FNV...
        GCD...
        R2R...
        """
        try:
            form = self.get_form()
        except:
            return HttpResponse('Bad request: num must be in range 1-5', status=400)

        # key = 'fld_name' for fld in request.FILES.keys():
        # form.instance.is_third_allowed = False
        # problem with files disappeared couldn't be solved in simple way without ajax etc.

        if form.is_valid():
            print("===VALID===")

            lang = form.cleaned_data['lang']
            main_file = form.cleaned_data['mf']
            secondary_files = [form.cleaned_data[s_f_name] for s_f_name in form.get_secondary_field_names()]

            task = Task(main_xml=main_file, language=lang, creator=request.user)
            # task = Task(main_xml=main_file, language=lang)
            task.save()

            for sec_file in secondary_files:
                a = Attachment(task=task, file=sec_file)
                a.save()

            return redirect("base:task_list_view")
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        print("GSU...")
        # return super(TaskCustomView, self).get_success_url()
        return render(self.request, self.template_name, context={})

    # TODO insert info line at top [kwargs]


class CustomLoginView(LoginView):
    success_url = 'base:task_list_view'
    template_name = 'login.html'

    def get_context_data(self, **kwargs):
        context = super(CustomLoginView, self).get_context_data(**kwargs)
        context['lgn'] = True
        return context


@login_required
def delete_task(request, t_id):
    hp = request.user.has_perm('base.delete_task')
    if hp:
        task = get_object_or_404(Task, id=t_id)
        task.delete()
    return redirect("base:task_list_view")


@login_required
def logout_view(request):
    logout(request)
    return redirect('base:task_list_view')


def output_annotation_template(request, a_id):

    annotation = get_object_or_404(Annotation, id=a_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s"' % (basename(annotation.file.name))

    response.write(open(annotation.file.path, mode='rt').read())

    # writer = csv.writer(response)
    # writer.writerow(['First row', 'Foo', 'Bar', 'Baz'])

    return response


def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('base:task_list_view')
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form})


@login_required
def allow_third_annotation(request, task_id):
    if request.user.has_perm('base.delete_task'):
        task = get_object_or_404(Task, id=task_id)
        task.is_third_allowed = True
        task.save()
        return redirect('base:task_list_view')
    else:
        return HttpResponse('Forbidden: no required user permissions', status=403)


def calc_aggrs(data):
    m = statistics.mean(data)
    try:
        v = statistics.variance(data)
    except statistics.StatisticsError as e:
        v = 0.0
    return {'mean': "%.4f" % m, 'variance': "%.4f" % v}


def lang_aggregation(lang):
    num = 0
    kappa = list()
    kappa2 = list()
    jaccard = list()
    for score in AScores.objects.filter(task__language=lang):
        kappa.append(score.kappa_score)
        kappa2.append(score.kappa2_score)
        jaccard.append(score.jaccard_score)
        num += 1

    d = dict()
    if num != 0:
        d['kappa'] = calc_aggrs(kappa)
        d['kappa2'] = calc_aggrs(kappa2)
        d['jaccard'] = calc_aggrs(jaccard)
    return d


def aggregations(request):

    context = {'aggr': True}

    lang_dict = dict()
    context['ldata'] = lang_dict

    for lang, _ in LANGUAGE_CHOICES:
        lang_dict[lang] = lang_aggregation(lang)

    return render(request, 'aggr.html', context=context)


