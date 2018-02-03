from unittest import TestCase

from .utils import kappa_calc, jaccard_sim


class TestKappa_calc(TestCase):

    def test_1(self):
        # scikit-learn.org/stable/modules/model_evaluation.html#cohen-kappa
        d1 = {'a': ['2'], 'b': ['0'], 'c': ['2'], 'd': ['2'], 'e': ['0'], 'f': ['1']}
        d2 = {'a': ['0'], 'b': ['0'], 'c': ['2'], 'd': ['2'], 'e': ['0'], 'f': ['2']}

        self.assertAlmostEqual(0.42857, kappa_calc(d1, d2), places=5)
        self.assertAlmostEqual(0.66667, jaccard_sim(d1, d2), places=5)
        self.assertAlmostEqual(0.42857, kappa_calc(d1, d2, modified=True), places=5)

    def test_2(self):
        d1 = {'a': ['1', '2', '3'], 'b': ['1', '2', '3']}
        d2 = {'a': ['1', '2', '3'], 'b': ['1', '2', '3']}

        """
        Kappa*
        Matrix without diagonal dominating:
        2/9 2/9 2/9
        2/9 2/9 2/9
        2/9 2/9 2/9
        """

        self.assertAlmostEqual(1.0, jaccard_sim(d1, d2), places=1)
        self.assertAlmostEqual(0.0, kappa_calc(d1, d2), places=1)       # Warning!
        self.assertAlmostEqual(1.0, kappa_calc(d1, d2, modified=True), places=1)

    def test_3(self):
        d1 = {'a': [1, 2], 'b': [1], 'c': [0]}
        d2 = {'a': [2], 'b': [0, 2], 'c': [0]}

        self.assertAlmostEqual(0.5, jaccard_sim(d1, d2), places=1)
        self.assertAlmostEqual(0.33, kappa_calc(d1, d2), places=2)
        self.assertAlmostEqual(0.33, kappa_calc(d1, d2, modified=True), places=2)

    def test_4(self):
        d1 = {'a': [1, 2]}
        d2 = {'a': [2, 1]}

        self.assertAlmostEqual(1.0, jaccard_sim(d1, d2), places=1)
        self.assertAlmostEqual(0.0, kappa_calc(d1, d2), places=2)
        self.assertAlmostEqual(1.0, kappa_calc(d1, d2, modified=True), places=2)

    def test_5(self):
        d1 = {'a': ['P1', 'P2', 'P3']}
        d2 = {'a': ['P1', 'P4']}

        self.assertAlmostEqual(0.25, jaccard_sim(d1, d2), places=1)
        self.assertAlmostEqual(0.0, kappa_calc(d1, d2), places=2)
        self.assertAlmostEqual(0.0, kappa_calc(d1, d2, modified=True), places=2)

    def test_6(self):
        d1 = {'a': ['P1', 'P2', 'P3']}
        d2 = {'a': ['P1', 'P2', 'P4']}

        self.assertAlmostEqual(0.5, jaccard_sim(d1, d2), places=1)
        self.assertAlmostEqual(0.0, kappa_calc(d1, d2), places=2)
        self.assertAlmostEqual(2.0/7, kappa_calc(d1, d2, modified=True), places=2)