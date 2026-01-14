from app.ai.evaluator import evaluate_text

class QuestionParserAgent:
    def execute(self, context):
        context["parsed_subject"] = context["subject"]
        return context

class EvaluationAgent:
    def execute(self, context):
        score, details = evaluate_text(
            context["student_text"],
            context["rubric"]
        )
        context["score"] = score
        context["details"] = details
        return context

class FeedbackAgent:
    def execute(self, context):
        context["feedback"] = (
            "Good effort. Review the key concepts mentioned in the rubric."
            if context["score"] < 10
            else "Very good work. Answers are well structured."
        )
        return context
