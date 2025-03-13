from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain_community.llms import HuggingFacePipeline
from transformers import pipeline
from models import db, FAQ, Review
import numpy as np

class RAGSystem:
    def __init__(self, db_connection):
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Initialize LLM
        self.llm = HuggingFacePipeline.from_model_id(
            model_id="google/flan-t5-base",
            task="text2text-generation",
            model_kwargs={"temperature": 0.1, "max_length": 512}
        )
        
        # Connect to ChromaDB (persistent storage)
        self.vector_store = Chroma(
            collection_name="travel_data",
            embedding_function=self.embeddings,
            persist_directory="./chroma_db"
        )
        
        # Link with database connection
        self.db = db_connection

    def _load_faqs_into_vectorstore(self):
        """Load FAQs from SQL database into Chroma vector store"""
        faqs = self.db.session.query(FAQ).all()
        documents = [
            f"Question: {faq.question}\nAnswer: {faq.answer}" 
            for faq in faqs
        ]
        metadatas = [{"source": "faq", "id": faq.id} for faq in faqs]
        self.vector_store.add_texts(texts=documents, metadatas=metadatas)
        self.vector_store.persist()
    
    def _load_reviews_into_vectorstore(self):
        """Load reviews into ChromaDB"""
        reviews = self.db.session.query(Review).all()
        documents = [
            f"Review: {review.content}"
            for review in reviews
        ]
        metadatas = [
            {
                "source": "review",
                "user_id": review.user_id,
                "hotel_id": review.hotel_id
            }
            for review in reviews
        ]
        self.vector_store.add_texts(texts=documents, metadatas=metadatas)
        self.vector_store.persist()

    def add_faq_to_vectorstore(self, faq):
        """Incrementally add a single faq to the vector store"""
        document = f"Question: {faq.question}\nAnswer: {faq.answer}"
        metadata = {"source": "faq", "id": faq.id}
        self.vector_store.add_texts(texts=[document], metadatas=[metadata])
        self.vector_store.persist() 

    def add_review_to_vectorstore(self, review):
        """Incrementally add a single review to the vector store"""
        document = f"Review: {review.content}"
        metadata = {"source": "review", "user_id": review.user_id, "hotel_id":review.hotel_id}
        self.vector_store.add_texts(texts=[document], metadatas=[metadata])
        self.vector_store.persist() 

    def get_retriever(self, threshold=0.7):
        """Create a LangChain retriever with score threshold"""
        return self.vector_store.as_retriever(
            search_kwargs={"k": 3, "score_threshold": threshold}
        )

    def query_system(self, question, role="customer"):
        """Full RAG pipeline using LangChain components"""
        # Load both FAQs and Reviews. Use full methods during query initialization.
        self._load_faqs_into_vectorstore()
        self._load_reviews_into_vectorstore()
        
        # modify retriever for owners to focus on reviews
        if role=="property_owner":
            retriever=self.vector_store.as_retriever(search_kwargs={"k":5, "filter":{"source":"review"}})
        else:
            retriever=self.get_retriever()    
        
        # Create the QA chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )
        
        # Customize prompt based on user role
        if role == "property_owner":
            prompt_template = f"""
            You are an expert travel business advisor analyzing a query from a property owner. 
            The context provided below contains exclusively customer reviews about your property.
            Carefully analyze these reviews to extract key feedback, recurring themes, and actionable insights that can help improve your property’s performance.
            Use only the information provided in the context to base your analysis.
            
            Context: {{context}}
            
            Question: {{question}}
            
            Answer:
            """
        else:
            prompt_template = f"""
            You are a friendly and knowledgeable travel assistant. 
            The context provided below includes both frequently asked questions and customer reviews related to the query.
            Based solely on this context, provide a clear, concise, and helpful answer that addresses the customer's question. 
            Ensure your response is supportive and actionable, highlighting relevant details from the context.
            
            Context: {{context}}
            
            Question: {{question}}
            
            Helpful Answer:
            """
        
        # Execute the chain
        result = qa_chain({"query": question, "prompt": prompt_template})
        return {
            "answer": result["result"],
            "sources": [doc.metadata["source"] for doc in result["source_documents"]]
        }