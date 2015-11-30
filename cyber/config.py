import yaml

DEFAULT_POOL_SIZE = 20
DEFAULT_IDLE_TIME = 600
DEFAULT_BACKLOG = 20


def _load_default_settings():
    return dict(pool_size=DEFAULT_POOL_SIZE,
                idle_time=DEFAULT_IDLE_TIME,
                backlog=DEFAULT_BACKLOG)


class _Options(object):
    _inst = None
    _settings = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = object.__new__(cls)
            cls._settings = _load_default_settings()
        return cls._inst

    def __getattr__(self, name):
        if name in self._settings:
            return self._settings[name]
        raise AttributeError("Unrecognized option %r" % name)

    def __setattr__(self, name, value):
        self._settings[name] = value

    def __iter__(self):
        return (opt for opt in self._settings.keys())

    def __contains__(self, name):
        return name in self._settings

    def __getitem__(self, name):
        return self._settings[name]

    def get(self, name, default=None):
        return self._settings.get(name, default)

    def set(self, name, value):
        self._settings[name] = value

    def items(self):
        return [(n, v) for n, v in self._settings.items()]

    def as_dict(self):
        return dict((n, v) for n, v in self._settings.items())

    def load_yaml(self, filepath):
        self._settings.update(yaml.load(open(filepath).read()))


options = _Options()
