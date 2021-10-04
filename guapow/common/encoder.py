from json import JSONEncoder


class CustomJSONEncoder(JSONEncoder):

    def default(self, o):
        if isinstance(o, set):
            return [*o]

        return super(CustomJSONEncoder, self).default(o)
