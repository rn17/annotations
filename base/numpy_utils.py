import shutil
from tempfile import NamedTemporaryFile

import numpy as np
import csv
from sklearn.metrics import confusion_matrix, precision_score, f1_score
from .utils import ANN_FILE_DELIM, DATA_STARTS_COLUMN, ARTICLE_COLUMN_INDEX, convert_file_to_csv_reader_header, \
    CHART_SPLITS


def compare_files_path_entry(true_file_path, pred_file_path, output_file_path):
    return compare_files(open(true_file_path, mode='rt'), open(pred_file_path, mode='rt'), output_file_path)


def compare_files(true_file_descriptor, pred_file_descriptor, output_file_path):
    """

    :param output_file_path:
    :param pred_file_descriptor: nlp-machine-scoring
    :param true_file_descriptor: human-annotation
    :return:
    """
    def to_float(e):
        if not e:
            return 0.0
        else:
            return float(e)

    true_file_descriptor.seek(0)
    pred_file_descriptor.seek(0)

    true_reader, true_csv_header = convert_file_to_csv_reader_header(true_file_descriptor)
    pred_reader, pred_csv_header = convert_file_to_csv_reader_header(pred_file_descriptor)

    true_np = np.empty([0, len(true_csv_header[DATA_STARTS_COLUMN:])], dtype=bool)
    pred_np = np.empty([0, len(pred_csv_header[DATA_STARTS_COLUMN:])], dtype=float)
    for i, true_row in enumerate(true_reader):
        true_article = true_row[ARTICLE_COLUMN_INDEX]
        ba = np.array([[bool(e) for e in true_row[DATA_STARTS_COLUMN:]]])
        true_np = np.append(true_np, ba, axis=0)

        pred_row = next(pred_reader)
        pred_article = pred_row[ARTICLE_COLUMN_INDEX]

        assert true_article == pred_article, "%s: %s, %s" % (i, true_article, pred_article)   # same paragraphs
        ba = np.array([[to_float(e) for e in pred_row[DATA_STARTS_COLUMN:]]])
        pred_np = np.append(pred_np, ba, axis=0)

    assert true_np.shape == pred_np.shape, "%s, %s" % (true_np.shape, pred_np.shape)
    true_file_descriptor.close()
    pred_file_descriptor.close()

    true_flattened = true_np.flatten()

    output_csv_file = open(output_file_path, mode='wt')

    writer = csv.writer(output_csv_file, delimiter=ANN_FILE_DELIM)
    writer.writerow(['threshold', 'tp', 'tn', 'fp', 'fn', 'precision', 'recall', 'fscore'])

    points = np.linspace(0.0, 1, 1+CHART_SPLITS, endpoint=True)
    best_f_score = -1
    for threshold in points:
        b = pred_np >= threshold

        pred_flattened = b.flatten()
        assert true_flattened.shape == pred_flattened.shape

        precision = precision_score(true_flattened, pred_flattened)
        f1 = f1_score(true_flattened, pred_flattened)
        tn, fp, fn, tp = confusion_matrix(true_flattened, pred_flattened).ravel()
        if tp == 0:
            recall = 0.0
        elif (tp + fn) == 0:
            recall = 1.0
        else:
            recall = float(tp) / (tp + fn)

        writer.writerow(["%.4f" % threshold, tp, tn, fp, fn, precision, recall, f1])

        if f1 > best_f_score:
            best_f_score = f1

    best_f_score = "%s" % best_f_score

    output_csv_file.close()
    tempfile = NamedTemporaryFile(delete=False, mode="wt")

    with open(output_file_path, 'rt') as modified_output, tempfile:
        reader = csv.reader(modified_output, delimiter=ANN_FILE_DELIM)
        writer = csv.writer(tempfile, delimiter=ANN_FILE_DELIM)

        for row in reader:
            if row[7] == best_f_score:
                row[0] = row[0] + '*'
            writer.writerow(row)

    shutil.move(tempfile.name, output_file_path)
    return best_f_score


def top_values(pred_file_descriptor):
    """
    DBG to extract top from nlp scores
    :param pred_file_descriptor:
    :return:
    """

    pred_csv_header = pred_file_descriptor.readline()
    pred_columns = pred_csv_header.strip().split(ANN_FILE_DELIM)[DATA_STARTS_COLUMN:]

    assert ":" not in pred_csv_header[ARTICLE_COLUMN_INDEX]

    articles = []

    pred_np = np.empty([0, len(pred_columns)], dtype=float)
    pred_csv_reader = csv.reader(pred_file_descriptor, delimiter=ANN_FILE_DELIM, quotechar='"')
    for i, row in enumerate(pred_csv_reader):
        articles.append(row[ARTICLE_COLUMN_INDEX])
        ba = np.array([[float(e) for e in row[DATA_STARTS_COLUMN:]]])
        pred_np = np.append(pred_np, ba, axis=0)

        # print(ba[0])
        # print(len(pred_columns))

        sss = np.argsort(ba[0])
        top_index = sss[-1]
        sec_index = sss[-2]
        print(row[ARTICLE_COLUMN_INDEX], top_index, ba[0, top_index], pred_columns[top_index])
        print(">>>", sec_index, ba[0, sec_index], pred_columns[sec_index])


if __name__ == "__main__":
    compare_files_path_entry(
        '/home/antre/PyProjects/upw_annotation_service/manual_scores.csv',
        '/home/antre/PyProjects/upw_annotation_service/nlp_scores.csv',
        '/home/antre/PyProjects/upw_annotation_service/annotations/global_static/generated_scores.csv')
