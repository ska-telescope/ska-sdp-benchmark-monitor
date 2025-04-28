"""Docstring @todo."""

import os


class EnvGatherer:
    """Docstring @todo."""

    def read(self):
        """Docstring @todo."""

        data = {}
        for k in os.environ:
            data[k] = os.environ[k]
        return data
