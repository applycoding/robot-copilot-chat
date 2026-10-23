from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env


def test_routes():
    app = create_app(load_settings(env=default_settings_env(), dotenv_enabled=False))

    def collect(routes):
        out = set()
        for r in routes:
            if getattr(r, "original_router", None) is not None:
                out |= collect(r.original_router.routes)
            nested = getattr(r, "routes", None)
            if nested:
                out |= collect(nested)
            path = getattr(r, "path", None)
            methods = getattr(r, "methods", None)
            if path and methods is not None:
                out.add((frozenset(methods or ()), path))
        return out

    paths = collect(getattr(app, "router", app).routes)
    expected = {
        (frozenset({"GET"}), "/"),
        (frozenset({"GET"}), "/healthz"),
        (frozenset({"GET"}), "/api/site"),
        (frozenset({"POST"}), "/api/chat"),
        (frozenset({"POST"}), "/api/missions/{mission_id}/repair"),
        (frozenset({"POST"}), "/api/missions/{mission_id}/confirm"),
        (frozenset({"GET"}), "/api/missions/{mission_id}"),
        (frozenset({"GET"}), "/api/missions/{mission_id}/commands"),
        (frozenset({"GET"}), "/api/runs/{run_id}"),
    }
    for item in expected:
        assert item in paths, item
    c = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        app, base_url="http://localhost"
    )
    for p in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(p).status_code == 404
