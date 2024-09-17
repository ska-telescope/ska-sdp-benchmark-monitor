import os

class EnvGatherer:
    def read(self):
        data = {}
        for k in os.environ:
            data[k] = os.environ[k]
        return data
