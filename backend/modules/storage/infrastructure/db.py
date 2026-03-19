class Database:
    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def health(self) -> dict:
        return {
            "status": "connected" if self.connected else "disconnected",
            "driver": "stub",
        }