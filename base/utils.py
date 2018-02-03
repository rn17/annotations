import itertools
import os
from io import TextIOWrapper
from tempfile import TemporaryFile
from xml.etree import ElementTree as ET
import csv

import magic
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile

PROVISION_TAG = 'provision'
DOCUMENT_TAG = 'document'

TXT = "txt"
LBL = "label"
EMPTY = "EMPTY"

ANN_FILE_DELIM = ','
ARTICLE_COLUMN_INDEX = 1
DATA_STARTS_COLUMN = 2

CHART_SPLITS = 500

EN = 'EN'
FR = 'FR'
IT = 'IT'
LANGUAGE_CHOICES = ((EN, EN), (FR, FR), (IT, IT))


def process_xml(f_name, from_string=False):
    if not from_string:
        tree = ET.parse(f_name)
    else:
        tree = ET.ElementTree(ET.fromstring(f_name))
    root = tree.getroot()
    assert root.tag == DOCUMENT_TAG
    lst = list()
    for child in root:
        d = dict()
        assert child.tag == PROVISION_TAG
        if 'id' in child.attrib:
            d[LBL] = child.attrib['id']
        d[TXT] = child.text
        lst.append(d)

        some_text_after_tag = child.tail.strip()
        if some_text_after_tag:
            lst.append({TXT: some_text_after_tag})
    return lst


def parse_annotation_file(f_name):

    f_desc = open(f_name, mode='rt', buffering=-1)
    return parse_annotation_file_by_descriptor(f_desc)


def parse_annotation_file_by_descriptor(f_descriptor):
    header = f_descriptor.readline().strip().split(ANN_FILE_DELIM)
    assert ':' not in header[1], "data in columns 0-1: should be from 2"

    a_csv_reader = csv.reader(f_descriptor, delimiter=ANN_FILE_DELIM, quotechar='"')

    d = dict()
    for row in a_csv_reader:
        assert len(row) == len(header)
        key = row[1]
        assert key not in d
        d[key] = list()
        for inter_val, column in zip(row[DATA_STARTS_COLUMN:], header[DATA_STARTS_COLUMN:]):
            if inter_val:
                assert inter_val == '1', inter_val
                d[key].append(column)
        if not d[key]:
            d[key].append(EMPTY)
    f_descriptor.close()

    return d


def kappa_calc(a_dict, b_dict, modified=False):
    """
    dict must contain lists as values, if there is no features selected: ['EMPTY']

    :param modified: Kappa** activation
    :param a_dict: user A
    :param b_dict: user B
    :return: Kappa*
    """
    assert isinstance(a_dict, dict)
    assert isinstance(b_dict, dict)
    assert a_dict.keys() == b_dict.keys()
    # for kappa it's no matter about not-used tag_features [matrix has all 0s by processing them]
    # so, let's say we have features: .unique(values)
    features = set()
    for _, v in a_dict.items():
        assert isinstance(v, list)
        features.update(v)

    for _, v in b_dict.items():
        assert isinstance(v, list)
        features.update(v)

    features = list(features)
    features_num = len(features)

    #print(features)
    # let's not use numpy
    matrix = [[0.0 for _ in features] for _ in features]
    for k in a_dict.keys():
        a_features = a_dict[k]
        b_features = b_dict[k]

        # [P1, P2]x[P2, P3, P4] -> [(P1, P2), (P1, P3), (P1, P4), (P2, P2), (P2, P3), (P2, P4)]
        all_combos_ab = list(itertools.product(*[a_features, b_features]))
        each_cell_rate = 1.0 / len(all_combos_ab)

        for a, b in all_combos_ab:
            a_feature_index = features.index(a)
            b_feature_index = features.index(b)

            if modified:
                if (a, a) in all_combos_ab and (b, b) in all_combos_ab:
                    # (P1, P4): if (P1, P1) and (P4, P4) inside: (P1, P1)++, for (P4, P4) the same with (P4, P1)
                    a_feature_index = features.index(a)
                    b_feature_index = features.index(a)
            matrix[a_feature_index][b_feature_index] += each_cell_rate

    # matrix_sum should be == number of observations
    matrix_sum = sum(sum(line) for line in matrix)
    assert abs(matrix_sum - len(a_dict)) <= 0.001, "%s %s" % (matrix_sum, len(a_dict))

    p0 = sum(matrix[i][i] / matrix_sum for i in range(features_num))
    pe = 0.0
    for i in range(len(features)):
        sum_vert = sum(matrix[i][j] / matrix_sum for j in range(features_num))
        sum_horiz = sum(matrix[j][i] / matrix_sum for j in range(features_num))
        pe_by_i = sum_vert * sum_horiz
        pe += pe_by_i
    if abs(1.0 - pe) <= 0.001:
        kappa = 1.0             # division by zero
    elif pe > 1.0:
        raise AssertionError('too big dividend pe=%s' % pe)
    elif pe < 0.0:
        raise AssertionError('too small dividend pe=%s' % pe)
    else:
        kappa = (p0 - pe) / (1.0 - pe)
    return kappa


def jaccard_sim(d_a, d_b):
    assert isinstance(d_a, dict)
    assert isinstance(d_b, dict)
    assert d_a.keys() == d_b.keys()

    weight = 1.0/len(d_a.keys())
    score = 0.0

    for k in d_a.keys():
        d_a_val = d_a[k]
        assert isinstance(d_a_val, list)
        d_b_val = d_b[k]
        assert isinstance(d_b_val, list)

        intersect = len(set(d_a_val).intersection(set(d_b_val)))
        un = len(set(d_a_val).union(set(d_b_val)))

        score += weight*(float(intersect)/un)

    return score


def validate_file(upload):
    print("Validating...")

    fname = upload.file

    rrr = fname.read()
    try:
        process_xml(rrr, from_string=True)
    except Exception as e:
        raise ValidationError("Error with %s: %s" % (upload, e))

    file_type = magic.from_buffer(rrr, mime=True)
    if file_type != 'application/xml':
        raise ValidationError("%s: XML file required" % fname)


def convert_file_to_csv_reader_header(file_or_byte_stream):

    def decode_line(l):
        if isinstance(l, (bytes, bytearray)):
            return l.decode('utf-8')
        else:
            return l

    file_or_byte_stream.seek(0)
    file_data = file_or_byte_stream.readlines()

    file_generator = (decode_line(line) for line in file_data)
    reader = csv.reader(file_generator, delimiter=ANN_FILE_DELIM, quotechar='"')
    header = next(reader)

    return reader, header


def validate_ann_cell(str_value):
    return not str_value or str_value == '1'


def validate_nlp_cell(str_value):
    try:
        float(str_value)
        return True
    except Exception as e:
        print(e)
        return False


def ann_file_validator(upload):
    upload_file_validator(upload, validate_ann_cell)


def nlp_file_validator(upload):
    upload_file_validator(upload, validate_nlp_cell)


def upload_file_validator(upload, validate_func):

    assert isinstance(upload, (InMemoryUploadedFile, TextIOWrapper))

    reader, header = convert_file_to_csv_reader_header(upload)

    if ':' in header[ARTICLE_COLUMN_INDEX]:
        raise ValidationError('check column %s: it should be article column' % ARTICLE_COLUMN_INDEX)
    columns = header[DATA_STARTS_COLUMN:]
    if len(columns) != len(set(columns)):
        raise ValidationError('the same columns in header')

    articles = set()
    for i, line in enumerate(reader):
        if len(line) != len(header):
            raise ValidationError('line %s has different len with header' % i)
        article = line[ARTICLE_COLUMN_INDEX]
        if article in articles:
            raise ValidationError('multiple article "%s"' % article)
        articles.add(article)
        for j, e in enumerate(line[DATA_STARTS_COLUMN:]):
            if not validate_func(e):
                raise ValidationError('not allowed data at cell (%s, %s): %s' % (i, j, e))


def pairwise_skeleton_files_validator(ann_file_1, ann_file_2):
    """
    Used to control same column-row structure of 2 files (ann X ann, ann X nlp, nlp X nlp)
    :param ann_file_1:
    :param ann_file_2:
    :return:
    """
    assert isinstance(ann_file_1, (InMemoryUploadedFile, TextIOWrapper))
    assert isinstance(ann_file_2, (InMemoryUploadedFile, TextIOWrapper))

    reader_1, header_1 = convert_file_to_csv_reader_header(ann_file_1)
    reader_2, header_2 = convert_file_to_csv_reader_header(ann_file_2)

    if header_1 != header_2:
        raise ValidationError('headers differs')

    for row_1 in reader_1:
        row_2 = next(reader_2)
        article_1 = row_1[ARTICLE_COLUMN_INDEX]
        article_2 = row_2[ARTICLE_COLUMN_INDEX]
        if article_1 != article_2:
            raise ValidationError('articles differ (%s <-> %s)' % (article_1, article_2))


def get_filename_tail(field):
    if field:
        return os.path.basename(field.name)
    else:
        return None


def convert_to_tmp_file(in_memory_file):

    tf = TemporaryFile(mode='w+t')
    for line in in_memory_file:
        line = line.decode("utf-8")
        line = line.replace('\"', '')
        tf.write(line)

    tf.seek(0)
    return tf