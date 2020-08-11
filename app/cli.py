import click
from app.main.archive import apidoc


def register(app):
    @app.cli.group()
    def doc():
        """print api docs."""
        pass

    @doc.command()
    def printdoc():
        print("will print api doc")
        apidoc()
