from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from .filters import data

# Sample labeled data


X = [x[0] for x in data]
y = [x[1] for x in data]

model = make_pipeline(TfidfVectorizer(), MultinomialNB())
model.fit(X, y)

def classify_query(query):
    return model.predict([query])[0]
