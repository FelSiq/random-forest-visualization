"""Module dedicated to the visualization of a Decision Tree."""
import typing as t
import inspect
import collections

import sklearn.tree
import sklearn.ensemble
import sklearn.metrics
import sklearn.preprocessing
import numpy as np
import scipy.cluster.hierarchy
import pymfe.mfe

from . import serialize

try:
    from . import utils

except ImportError:
    pass

METRICS_CLASSIFICATION = {
    "accuracy": (sklearn.metrics.accuracy_score, None),
    "balanced_accuracy": (sklearn.metrics.balanced_accuracy_score, None),
    "roc_auc_binary": (sklearn.metrics.roc_auc_score, {
        "average": "binary"
    }),
    "roc_auc_micro": (sklearn.metrics.roc_auc_score, {
        "average": "micro"
    }),
    "roc_auc_macro": (sklearn.metrics.roc_auc_score, {
        "average": "macro"
    }),
    "roc_auc_weighted": (sklearn.metrics.roc_auc_score, {
        "average": "weighted"
    }),
    "average_precision_binary": (sklearn.metrics.average_precision_score, {
        "average": "binary"
    }),
    "average_precision_micro": (sklearn.metrics.average_precision_score, {
        "average": "micro"
    }),
    "average_precision_macro": (sklearn.metrics.average_precision_score, {
        "average": "macro"
    }),
    "average_precision_weighted": (sklearn.metrics.average_precision_score, {
        "average": "weighted"
    }),
    "precision_binary": (sklearn.metrics.precision_score, {
        "average": "binary"
    }),
    "precision_micro": (sklearn.metrics.precision_score, {
        "average": "micro"
    }),
    "precision_macro": (sklearn.metrics.precision_score, {
        "average": "macro"
    }),
    "precision_weighted": (sklearn.metrics.precision_score, {
        "average": "weighted"
    }),
    "recall_binary": (sklearn.metrics.recall_score, {
        "average": "binary"
    }),
    "recall_micro": (sklearn.metrics.recall_score, {
        "average": "micro"
    }),
    "recall_macro": (sklearn.metrics.recall_score, {
        "average": "macro"
    }),
    "recall_weighted": (sklearn.metrics.recall_score, {
        "average": "weighted"
    }),
}  # type: t.Dict[str, t.Tuple[t.Callable[[np.ndarray, np.ndarray], float], t.Optional[t.Dict[str, t.Any]]]]
"""Chosen metrics to evaluate classifier models."""

METRICS_REGRESSION = {
    "mean_absolute_error": (sklearn.metrics.mean_absolute_error, None),
    "mean_squared_log_error": (sklearn.metrics.mean_squared_log_error, None),
    "explained_variance_score":
    (sklearn.metrics.explained_variance_score, None),
    "mean_squared_error": (sklearn.metrics.mean_squared_error, None),
    "median_absolute_error": (sklearn.metrics.median_absolute_error, None),
}  # type: t.Dict[str, t.Tuple[t.Callable[[np.ndarray, np.ndarray], float], t.Optional[t.Dict[str, t.Any]]]]
"""Chosen metrics to evaluate regressor models."""


def get_tree_structure(tree: sklearn.tree._tree.Tree) -> t.Dict[str, t.Any]:
    """Transform the sklearn tree structure into a string object.

    For more information, check the sklearn documentation (url below.)
    https://scikit-learn.org/stable/auto_examples/tree/plot_unveil_tree_structure.html
    """
    attributes = inspect.getmembers(tree,
                                    lambda attr: not inspect.isroutine(attr))

    encoded_tree = {
        utils.preprocess_key(attr_name):
        serialize.json_encoder_type_manager(attr_val)
        for attr_name, attr_val in attributes
        if not (attr_name.startswith('__') and attr_name.endswith('__'))
    }

    return encoded_tree


def get_class_freqs(
    dt_model: sklearn.ensemble.RandomForestClassifier, instance: np.ndarray
) -> t.Tuple[t.Optional[t.Dict[str, t.Dict[str, str]]], t.Optional[str]]:
    """Get the frequency of every class from a RF Classifier prediction."""
    if not isinstance(dt_model, sklearn.ensemble.RandomForestClassifier):
        return None, None

    class_by_tree = {str(class_label): 0
                     for class_label in dt_model.classes_
                     }  # type: t.Dict[str, int]

    for tree in dt_model.estimators_:
        pred_class = tree.predict(instance).astype(dt_model.classes_.dtype)
        class_by_tree[str(pred_class[0])] += 1

    sorted_class_by_tree = sorted(class_by_tree.items(),
                                  key=lambda item: item[1],
                                  reverse=True)

    ret = collections.OrderedDict((key, {
        "value": {
            "value": value,
            "proportion": value / dt_model.n_estimators,
        },
        "description":
        "Number of trees in the forest that predicted class '{}'.".format(key),
    }) for key, value in sorted_class_by_tree)

    margin = None  # type: t.Optional[str]

    if len(class_by_tree) > 1:
        margin = "{:.2f}".format(
            (sorted_class_by_tree[0][1] - sorted_class_by_tree[1][1]) /
            dt_model.n_estimators)

    return ret, margin


def hot_encoding(labels: np.ndarray) -> np.ndarray:
    """One-Hot Encoding labels."""
    if labels.ndim == 1:
        labels = labels.reshape(-1, 1)

    labels_ohe = sklearn.preprocessing.OneHotEncoder().fit_transform(
        labels).todense()

    return labels_ohe


def get_metrics(
    dt_model: t.Union[sklearn.ensemble.RandomForestClassifier,
                      sklearn.ensemble.RandomForestRegressor,
                      sklearn.tree.DecisionTreeRegressor,
                      sklearn.tree.DecisionTreeClassifier],
    preds: np.ndarray,
    true_labels: np.ndarray,
    preds_proba: t.Optional[np.ndarray] = None,
    true_labels_ohe: t.Optional[np.ndarray] = None,
) -> t.Dict[str, t.Any]:
    """Evaluate given DT/RF models using some chosen metrics."""
    def safe_call_func(func: t.Callable[[np.ndarray, np.ndarray], float],
                       args: t.Optional[t.Dict[str, t.Any]],
                       true_labels: np.ndarray,
                       preds: np.ndarray) -> t.Optional[str]:
        """Call an evaluation metric, catching ValueError exceptions."""
        if args is None:
            args = {}

        try:
            res = func(true_labels, preds, **args)  # type: t.Union[str, float]

            if res is not None:
                res = "{:.2f}".format(res)

            return res

        except ValueError:
            return None

    chosen_metrics = None

    if isinstance(dt_model, (sklearn.ensemble.RandomForestClassifier,
                             sklearn.tree.DecisionTreeClassifier)):
        chosen_metrics = METRICS_CLASSIFICATION

    if isinstance(dt_model, (sklearn.ensemble.RandomForestRegressor,
                             sklearn.tree.DecisionTreeRegressor)):
        chosen_metrics = METRICS_REGRESSION

    if chosen_metrics:
        return {
            metric_name: {
                "value": safe_call_func(*metric_pack, true_labels, preds),
                "description": "Todo.",
            }
            for metric_name, metric_pack in chosen_metrics.items()
        }

    return {}


def top_most_common_attr_seq(
    dt_model: t.Union[sklearn.ensemble.RandomForestClassifier,
                      sklearn.ensemble.RandomForestRegressor,
                      sklearn.tree.DecisionTreeRegressor,
                      sklearn.tree.DecisionTreeClassifier],
    seq_num: int = 10,
    include_node_decision: bool = False,
) -> t.Tuple[t.Tuple[t.Tuple[int, ...]], t.Tuple[float]]:
    """."""
    def _traverse_tree(tree: t.Union[sklearn.tree.DecisionTreeRegressor,
                                     sklearn.tree.DecisionTreeClassifier],
                       cur_ind: int, cur_attr_seq: t.List[int]) -> None:
        """Traverse a tree recursively through all possible paths."""
        if tree.feature[cur_ind] < 0:
            path = tuple(cur_attr_seq)
            seqs.setdefault(path, 0)
            seqs[path] += tree.weighted_n_node_samples[cur_ind]
            return

        if include_node_decision:
            cur_attr_seq.append((tree.feature[cur_ind], "<="))
            _traverse_tree(tree, tree.children_left[cur_ind], cur_attr_seq)
            cur_attr_seq.pop()

            cur_attr_seq.append((tree.feature[cur_ind], ">"))
            _traverse_tree(tree, tree.children_right[cur_ind], cur_attr_seq)
            cur_attr_seq.pop()

        else:
            cur_attr_seq.append(tree.feature[cur_ind])
            _traverse_tree(tree, tree.children_left[cur_ind], cur_attr_seq)
            _traverse_tree(tree, tree.children_right[cur_ind], cur_attr_seq)
            cur_attr_seq.pop()

    seqs = {}  # type: t.Dict[t.Tuple[int, ...], int]

    try:
        trees = dt_model.estimators_

    except AttributeError:
        trees = [dt_model]

    for tree in trees:
        _traverse_tree(tree.tree_, cur_ind=0, cur_attr_seq=[])

    if seqs:
        sorted_seqs, abs_freqs = zip(
            *sorted(seqs.items(), key=lambda item: item[1], reverse=True))
        freqs = tuple(np.asarray(abs_freqs, dtype=np.float) / sum(abs_freqs))

    else:
        sorted_seqs = freqs = tuple()

    if seq_num >= len(sorted_seqs):
        return sorted_seqs, freqs

    return sorted_seqs[:seq_num], freqs[:seq_num]


def calc_dna_dist_mat(model: t.Union[sklearn.ensemble.RandomForestClassifier,
                                     sklearn.ensemble.RandomForestRegressor],
                      X: np.ndarray) -> np.ndarray:
    """Calculate DNA distance matrix between trees."""
    inst_num = X.shape[0]
    dna = np.zeros((model.n_estimators, inst_num), dtype=X.dtype)

    for tree_ind, tree in enumerate(model.estimators_):
        dna[tree_ind, :] = tree.predict(X)

    # Shift Cohen's Kappa to prevent negative values, and also transform
    # it to a distance measure (i.e., the higher is the correlation, the
    # smaller will be the dna_dists value.)
    # Note: this distance measure is in [0, 2], with 0 being 'totally
    # equal' and 2 being 'totally distinct.'
    dna_dists = 1.0 - scipy.spatial.distance.pdist(
        X=dna, metric=sklearn.metrics.cohen_kappa_score)

    return dna_dists


def calc_mtf_dist_mat(model: t.Union[sklearn.ensemble.RandomForestClassifier,
                                     sklearn.ensemble.RandomForestRegressor]) -> np.ndarray:
    """."""
    mtf_names = pymfe.mfe.MFE.valid_metafeatures(groups="model-based")
    summary = ("mean", "sd")
    mtf_vec = np.zeros((model.n_estimators, len(summary) * len(mtf_names)), dtype=float)

    # TODO: extract.
    mtf_vec = np.random.random(mtf_vec.shape)

    mtf_min = mtf_vec.min(axis=0)
    mtf_vec = (mtf_vec - mtf_min) / (mtf_vec.max(axis=0) - mtf_min)

    mtf_dists = scipy.spatial.distance.pdist(
        X=mtf_vec, metric="euclidean")

    return mtf_dists


def get_hierarchical_cluster(dist_mat: np.ndarray,
                             threshold_cut: t.Union[int, float],
                             linkage: str) -> t.Dict[str, np.ndarray]:
    """."""
    dendrogram = scipy.cluster.hierarchy.linkage(dist_mat, method=linkage)

    optimal_leaves_seq = scipy.cluster.hierarchy.leaves_list(
        scipy.cluster.hierarchy.optimal_leaf_ordering(dendrogram, dist_mat))

    clust_assignment = scipy.cluster.hierarchy.fcluster(dendrogram,
                                                        t=threshold_cut,
                                                        criterion="distance")

    _, dendrogram_tree = scipy.cluster.hierarchy.to_tree(dendrogram, rd=True)

    num_cluster = np.unique(clust_assignment).size

    sqr_dist_mat = scipy.spatial.distance.squareform(dist_mat)

    clust_buckets = []
    for i in np.arange(1, 1 + num_cluster):
        clust_inst_inds = tuple(np.flatnonzero(clust_assignment == i))

        if len(clust_inst_inds) > 2:
            medoid_ind = clust_inst_inds[np.argmin(
                np.sum(sqr_dist_mat[tuple(
                    np.meshgrid(clust_inst_inds, clust_inst_inds))],
                       axis=0))]

        else:
            medoid_ind = clust_inst_inds[0]

        clust_buckets.append({
            "tree_inds": clust_inst_inds,
            "medoid_ind": medoid_ind,
        })

    return {
        "dendrogram": dendrogram,
        "dendrogram_tree": dendrogram_tree,
        "clust_assignment": clust_buckets,
        "num_cluster": num_cluster,
        "optimal_leaves_seq": optimal_leaves_seq,
    }


def get_toy_model(forest: bool = True, regressor: bool = False):
    """Create a DT/RF toy model for testing purposes."""
    from sklearn.datasets import load_iris
    iris = load_iris()  # type: sklearn.utils.Bunch

    X = iris.data
    y = iris.target
    attr_labels = iris.feature_names

    algorithms = {
        (False, False): sklearn.tree.DecisionTreeClassifier,
        (False, True): sklearn.tree.DecisionTreeRegressor,
        (True, False): sklearn.ensemble.RandomForestClassifier,
        (True, True): sklearn.ensemble.RandomForestRegressor,
    }

    if forest:
        args = {
            "n_estimators": 10,
            "min_samples_split": 35,
            "min_samples_leaf": 20,
        }
    else:
        args = {}

    model = algorithms.get((forest, regressor),
                           sklearn.tree.DecisionTreeClassifier)(**args)
    model.fit(iris.data, iris.target)

    return model, X, y, attr_labels


if __name__ == "__main__":
    print(serialize.serialize_decision_tree(get_toy_model()))
