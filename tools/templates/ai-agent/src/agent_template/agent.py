class Agent:
    name = "__NAME__"

    def run(self, payload: dict[str, object]) -> dict[str, object]:
        return {"agent": self.name, "status": "ok", "payload": payload}
