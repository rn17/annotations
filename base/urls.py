from django.conf.urls import url, include

from .views import TaskListView, CreateTaskView, metrics_single, metrics_join, metrics_own, aggregations, aaa
from .views import make_annotation, submit_annotation, delete_task, output_annotation_template, allow_third_annotation
from .views import ann_cmp_2

app_name = "base"

urlpatterns = [

    url(r'^$', TaskListView.as_view(), name='task_list_view'),
    url(r'^annotate/(?P<a_id>\d+)/$', make_annotation, name='add_annotation'),      # TODO with resolvers <int:a_id>
    url(r'^inner_submit_annotation/$', submit_annotation, name='submit_annotation'),
    url(r'^download_annotation/(?P<a_id>\d+)/$', output_annotation_template, name='download_a'),
    url(r'^inner_allow_3rd/(?P<task_id>\d+)/$', allow_third_annotation, name='allow3'),

    url(r'^add_task/$', CreateTaskView.as_view(), name='add_task'),
    url(r'^inner_delete_task/(?P<t_id>\d+)/$', delete_task, name='delete_task'),

    url(r'^aggr/$', aggregations, name='aggr'),
    url(r'^dbg_aaa/$', aaa, name='aaa'),
    url(r'^ann_cmp_2/$', ann_cmp_2, name='ann_cmp_2'),

    url(r'^metrics_own/$', metrics_own, name='metrics_own'),
    url(r'^metrics_single/(?P<a_id>\d+)/$', metrics_single, name='metrics_single'),
    url(r'^metrics_join/(?P<a1_id>\d+)_(?P<a2_id>\d+)_(?P<mode>[ui])/$', metrics_join, name='metrics_join'),
]

