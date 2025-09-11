from render.markdown_live import MarkdownStream


class DummyConsole:
    def __init__(self):
        self.printed = []

    def print(self, text):
        self.printed.append(str(text))


class DummyLive:
    def __init__(self):
        self.console = DummyConsole()
        self.updated = []
        self.stopped = False

    def update(self, text):
        self.updated.append(str(text))

    def refresh(self):
        pass

    def stop(self):
        self.stopped = True


def test_waiting_and_update_flow(monkeypatch):
    ms = MarkdownStream()

    # Monkeypatch _ensure_live to inject DummyLive instead of real Live
    def ensure_live():
        if not ms.live:
            ms.live = DummyLive()

    ms._ensure_live = ensure_live  # type: ignore

    # Start waiting indicator
    ms.start_waiting("Loading…")
    assert ms.waiting_active is True
    assert ms.waiting_message == "Loading…"

    # Provide first content; waiting should stop automatically
    ms.update("Hello world", final=False)
    assert ms.waiting_active is False

    # Finalize output
    ms.update("Hello world", final=True)
    assert ms.live is None  # stop() clears live

