from app.agent_engine.tools.text_tools import compute_match_score, extract_keywords


def test_extract_keywords_keeps_domain_terms():
    text = "FastAPI PostgreSQL RabbitMQ Redis FastAPI"
    keywords = extract_keywords(text, top_n=4)

    assert "fastapi" in keywords
    assert "postgresql" in keywords


def test_compute_match_score():
    matched, missing, score = compute_match_score(
        ["fastapi", "postgresql", "rabbitmq"],
        "I use FastAPI and PostgreSQL in production.",
    )

    assert matched == ["fastapi", "postgresql"]
    assert missing == ["rabbitmq"]
    assert score == 66
