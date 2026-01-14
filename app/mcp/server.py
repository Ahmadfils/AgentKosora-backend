from app.mcp.agents import (
    QuestionParserAgent,
    EvaluationAgent,
    FeedbackAgent
)

class MCPServer:
    def __init__(self):
        self.agents = [
            QuestionParserAgent(),
            EvaluationAgent(),
            FeedbackAgent()
        ]

    def run(self, context: dict):
        for agent in self.agents:
            context = agent.execute(context)
        return context

mcp_server = MCPServer()
