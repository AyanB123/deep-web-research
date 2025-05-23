from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import Config
from utils import log_action

class KnowledgeBase:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=Config.GEMINI_API_KEY
        )
        self.vectordb = Chroma(
            persist_directory=Config.CHROMA_DB_PATH,
            embedding_function=self.embeddings
        )

    def store_data(self, data: list):
        texts = [d["content"] for d in data if d["content"]]
        metadatas = [{"url": d["url"]} for d in data if d["content"]]
        if texts:
            log_action(f"Storing {len(texts)} documents in knowledge base")
            self.vectordb.add_texts(texts, metadatas=metadatas)
            self.vectordb.persist()

    def retrieve_data(self, query: str, k=5):
        log_action(f"Retrieving data for query: {query}")
        return self.vectordb.similarity_search(query, k=k)
