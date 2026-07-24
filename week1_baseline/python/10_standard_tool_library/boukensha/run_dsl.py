class RunDSL:
    """The object passed to run()'s block. Exposes only `tool`, keeping the
    DSL surface intentionally small."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def tool(self, name, *, description, parameters=None):
        return self.registry.tool(name, description=description, parameters=parameters)
