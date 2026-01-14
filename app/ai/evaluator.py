def evaluate_text(student_text: str, rubric: str):
    words = student_text.lower().split()
    keywords = rubric.lower().split()

    matches = sum(1 for word in keywords if word in words)
    score = min(20, matches * 2)

    details = {
        "keywords_matched": matches,
        "total_keywords": len(keywords)
    }

    return score, details
