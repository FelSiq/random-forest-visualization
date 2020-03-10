"""App module of the DT/TF visualization backend."""

import typing as t
import re
import collections
import os
import pickle

import flask
import flask_cors
import flask_restful
import flask_restful.reqparse
import flask_session
import werkzeug
import numpy as np
import pandas as pd
import sklearn.tree
import redis

from . import model_dt
from . import serialize

NULL_VALUES = {
    "null",
    "nan",
    "na",
    "none",
    "noone",
    "",
    "nil",
}
"""Values in the instances to be interpreted as missing values."""

RE_EMPTY_SPACE = re.compile(r"\s+|%20")
"""Regular expression for empty spaces to preprocess given instances."""



class DecisionTree(flask_restful.Resource):
    """Class dedicated to serialize and jsonify a sklearn DT/RF model."""
    def __init__(self,
                 model,
                 X: np.ndarray,
                 y: np.ndarray,
                 attr_labels: t.Optional[t.Sequence[str]] = None):
        """."""
        self.model = model
        self.X = X
        self.y = y
        self.attr_labels = attr_labels

    def get(self):
        """Serialize and jsonify a sklearn RF/DT model."""
        return flask.jsonify(
            serialize.serialize_decision_tree(dt_model=self.model,
                                              attr_labels=self.attr_labels))


class PredictDataset(flask_restful.Resource):
    """Class dedicated to give methods for predicting a whole dataset."""
    def __init__(self,
                 model,
                 X: np.ndarray,
                 y: np.ndarray,
                 attr_labels: t.Optional[t.Sequence[str]] = None):
        """."""
        self.model = model
        self.X = X
        self.y = y
        self.attr_labels = attr_labels

        self.reqparse = flask_restful.reqparse.RequestParser()

        self.reqparse.add_argument("file",
                                   type=werkzeug.datastructures.FileStorage,
                                   location="files")

        self.reqparse.add_argument("sep", type=str, location="form")

        self.reqparse.add_argument("hasHeader", type=str, location="form")

        self.reqparse.add_argument("hasClasses", type=str, location="form")

    def post(self):
        """Make predictions and give metrics for the user-given dataset."""
        args = self.reqparse.parse_args()

        dataset_file = args["file"]
        sep = args["sep"]
        has_header = args["hasHeader"] == 'True'
        has_classes = args["hasClasses"] == 'True'

        data = pd.read_csv(filepath_or_buffer=dataset_file,
                           sep=sep,
                           header="infer" if has_header else None)

        if has_classes:
            X = data.iloc[:, :-1].values
            y = data.iloc[:, -1].values
            y_ohe = None  # model_dt.hot_encoding(y)
            preds_proba = None  # self.model.predict_proba(X)

        else:
            X = data.values
            y = None
            y_ohe = None
            preds_proba = None

        preds = self.model.predict(X)

        return flask.jsonify(
            model_dt.get_metrics(dt_model=self.model,
                                 preds=preds,
                                 true_labels=y,
                                 preds_proba=preds_proba,
                                 true_labels_ohe=y_ohe))


class PredictSingleInstance(flask_restful.Resource):
    """Class dedicated to provide methods for predicting a single instance."""
    def __init__(self,
                 model,
                 X: np.ndarray,
                 y: np.ndarray,
                 attr_labels: t.Optional[t.Sequence[str]] = None):
        """."""
        self.model = model
        self.X = X
        self.y = y
        self.attr_labels = attr_labels

    @staticmethod
    def _preprocess_instance(instance: str,
                             sep: str = ",") -> t.Optional[np.ndarray]:
        """Preprocess the user-given single instance."""
        preproc_inst = np.array(RE_EMPTY_SPACE.sub("", instance).split(sep))

        if not set(map(str.lower, preproc_inst)).isdisjoint(NULL_VALUES):
            return None

        return preproc_inst.astype(np.float32).reshape(1, -1)

    @staticmethod
    def _handle_errors(
            err_code: t.Sequence[str]) -> t.Dict[str, t.Dict[str, str]]:
        """Handle probable errors found while predicting the instance."""
        err_msg = {}

        if "ERROR_MISSING_VAL" in err_code:
            err_msg["error"] = {
                "value": "Currently missing values are not supported."
            }

        return err_msg

    def _decision_path(self,
                       inst_proc: np.ndarray) -> t.Sequence[t.Sequence[int]]:
        """Get the decision path of the instace for every tree in the model."""
        if isinstance(self.model, (sklearn.tree.DecisionTreeClassifier,
                                   sklearn.tree.DecisionTreeRegressor)):
            nodes = [self.model.decision_path(inst_proc).indices]

        else:
            dec_path, indices = self.model.decision_path(inst_proc)

            nodes = []
            base_index = 0
            next_tree_id = 0

            for value in dec_path.indices:
                if value == indices[next_tree_id]:
                    base_index = value
                    next_tree_id += 1
                    nodes.append([])

                nodes[-1].append(value - base_index)

        return nodes

    def get(self, instance: str):
        """Predict single instance and provide information."""
        inst_proc = PredictSingleInstance._preprocess_instance(instance)
        err_code = []

        if inst_proc is None:
            err_code.append("ERROR_MISSING_VAL")

        if err_code:
            return flask.jsonify(
                PredictSingleInstance._handle_errors(err_code))

        classes_by_tree, margin = model_dt.get_class_freqs(
            self.model, inst_proc)

        pred_vals = serialize.json_encoder_type_manager(
            collections.OrderedDict((
                ("prediction_result", {
                    "value": self.model.predict(inst_proc)[0],
                    "description": "Final value predicted by the model.",
                }),
                ("classes_by_tree", {
                    "value":
                    classes_by_tree,
                    "description":
                    "Frequency of every class "
                    "for every tree in the model.",
                }),
                ("margin", {
                    "value":
                    margin,
                    "description":
                    "Margin is the instance highest class probability "
                    "minus second highest class probability.",
                }),
                ("decision_path", {
                    "value": self._decision_path(inst_proc),
                }),
                ("leaf_id", {
                    "value": self.model.apply(inst_proc)[0],
                }),
            )))

        return flask.jsonify(pred_vals)


class MostCommonAttrSeq(flask_restful.Resource):
    """Find the most common sequence of attributes in the forest."""
    def __init__(self, model, **kwargs):
        self.model = model

    def get(self,
            seq_num: int = 10,
            include_node_decision: t.Union[int, bool] = False):
        top_common_seqs = model_dt.top_most_common_attr_seq(
            self.model,
            seq_num=seq_num,
            include_node_decision=include_node_decision > 0)

        return flask.jsonify(
            serialize.json_encoder_type_manager(top_common_seqs))


class ForestHierarchicalClustering(flask_restful.Resource):
    """Perform a hierarchical clustering using each tree DNA."""
    def __init__(self, model, X: np.ndarray, **kwargs):
        self.model = model
        self.X = X

        self.reqparse_post = flask_restful.reqparse.RequestParser()
        self.reqparse_post.add_argument("threshold_cut", type=float)
        self.reqparse_post.add_argument("linkage", type=str)
        self.reqparse_post.add_argument("strategy", type=str)

        self.reqparse_update = flask_restful.reqparse.RequestParser()
        self.reqparse_update.add_argument("threshold_cut", type=float)

    def post(self):
        args = self.reqparse_post.parse_args()

        threshold_cut = args.get("threshold_cut", 2.0)
        linkage = args.get("linkage", "average")
        strategy = args.get("strategy", "dna")

        if strategy not in ("dna", "metafeatures"):
            raise ValueError(
                "'strategy' must be either 'dna' or 'metafeatures.'")

        if strategy == "dna":
            dist_mat = model_dt.calc_dna_dist_mat(model=self.model, X=self.X)

        else:
            dist_mat = model_dt.calc_mtf_dist_mat(model=self.model)

        hier_clus_data = model_dt.get_hierarchical_cluster(dist_mat=dist_mat,
                                                 linkage=linkage)

        hier_clus_data.update(
            model_dt.make_hier_clus_cut(dendrogram=hier_clus_data.get("dendrogram"),
                                        dist_mat=dist_mat,
                                        threshold_cut=threshold_cut))

        flask.session["hier_clus_data"] = hier_clus_data
        flask.session["dist_mat"] = dist_mat

        response = flask.jsonify(serialize.json_encoder_type_manager(hier_clus_data))

        response.headers.add("Access-Control-Allow-Methods",
                             "GET, POST, OPTIONS, PUT, PATCH, DELETE")
        response.headers.add(
            "Access-Control-Allow-Headers",
            "Origin, X-Requested-With, Content-Type, Accept, x-auth")

        return response

    def put(self):
        args = self.reqparse_update.parse_args()

        threshold_cut = args.get("threshold_cut", 2.0)

        hier_clus_data = flask.session.get("hier_clus_data")
        dist_mat = flask.session.get("dist_mat")

        if hier_clus_data is None:
            raise ValueError("No hierarchical clustering hier_clus_data found.")

        hier_clus_data = model_dt.make_hier_clus_cut(dendrogram=hier_clus_data.get("dendrogram"),
                                           dist_mat=dist_mat,
                                           threshold_cut=threshold_cut)
        flask.session["hier_clus_data"].update(hier_clus_data)

        return flask.jsonify(serialize.json_encoder_type_manager(hier_clus_data))

    def delete(self):
        if flask.session.get("data"):
            print("Successfully deleted session data.")
            flask.session.pop("data")


class Config:
    """Set Flask configuration vars from .env file."""
    FLASK_ENV = os.environ.get("FLASK_ENV")
    FLASK_APP = os.environ.get("FLASK_APP")
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG")
    SESSION_TYPE = os.environ.get("SESSION_TYPE", "redis")
    SECRET_KEY = os.environ.get("SECRET_KEY")


sess = flask_session.Session()

def create_app():
    """DT visualization application factory."""
    app = flask.Flask(__name__, instance_relative_config=False)

    app.config.from_object(Config)

    flask_cors.CORS(app, supports_credentials=True)
    api = flask_restful.Api(app)

    dt_model, X, y, attr_labels = model_dt.get_toy_model()

    common_kwargs = {
        "model": dt_model,
        "X": X,
        "y": y,
        "attr_labels": attr_labels,
    }

    api.add_resource(DecisionTree,
                     "/dt-visualization",
                     resource_class_kwargs=common_kwargs)

    api.add_resource(PredictSingleInstance,
                     "/predict-single-instance/<string:instance>",
                     resource_class_kwargs=common_kwargs)

    api.add_resource(PredictDataset,
                     "/predict-dataset",
                     resource_class_kwargs=common_kwargs)

    api.add_resource(
        MostCommonAttrSeq,
        "/most-common-attr-seq/<int:seq_num>/<int:include_node_decision>",
        resource_class_kwargs=common_kwargs)

    api.add_resource(ForestHierarchicalClustering,
                     "/forest-hierarchical-clustering",
                     resource_class_kwargs=common_kwargs)

    sess.init_app(app)

    return app
