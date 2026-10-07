from app import cli
from conftest import ROOT


def test_printdoc_matches_docs_api_doc(make_app):
    """docs/api-doc.md is generated with: flask doc printdoc > docs/api-doc.md"""
    app = make_app()
    cli.register(app)
    result = app.test_cli_runner().invoke(args=["doc", "printdoc"])
    assert result.exit_code == 0
    for section in ("## Responses", "## store", "## get", "## hash", "## list", "## delete", "## health"):
        assert section in result.output
    assert result.output == (ROOT / "docs" / "api-doc.md").read_text(), \
        "docs/api-doc.md is out of date, run: flask doc printdoc > docs/api-doc.md"
