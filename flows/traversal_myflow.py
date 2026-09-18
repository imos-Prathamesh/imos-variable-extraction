# Source : flows/traversal_myflow.py
# Analogy: Blank blueprint — copy this file to create any new flow. Not used in production, just a starter template.
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import ConnectionTreeMixin  # or ImosMixin or both
from core.db import query, normalize
from core.branches import STATE_CONISITU  # whatever entry state applies


class TraversalMyFlow(ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query("SELECT COL FROM dbo.MY_TABLE WHERE NAME = ?", (self.article,))
        for row in rows:
            val = normalize(row["COL"])
            if val:
                path = [f"myflow({self.article})", f"COL={val}"]
                self._classify(val, STATE_CONISITU, path, "MY_TABLE", "COL")
        return self.result


def extract_myflow(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalMyFlow(article, max_depth).run()