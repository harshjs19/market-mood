from transformers import pipeline

sentiment_model = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert"
)

result = sentiment_model(
    "Tesla stock surged after strong earnings."
)

print(result)