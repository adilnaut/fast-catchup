from sentence_transformers import SentenceTransformer
import pickle


def setup_sentence_embeddings_model():
    model = SentenceTransformer('paraphrase-MiniLm-L6-v2')
    model_filepath = os.path.join('file_store', '2023-02-22-embedding-model')
    model_pickle = open(model_filepath, 'wb')
    pickle.dump(model, model_pickle)

def setup_sentiment_analysis_model():
    pipeline("sentiment-analysis")


if __name__ == '__main__':
    setup_sentence_embeddings_model()
    setup_sentence_embeddings_model()
