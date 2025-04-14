from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.llms import HuggingFacePipeline
from langchain_community.cache import SQLiteCache #added this for caching query results
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough, RunnableParallel
from langchain.schema.output_parser import StrOutputParser
from langchain.docstore.document import Document
import hashlib #for generating cache keys
from transformers import pipeline
from models import db, FAQ, Review
import numpy as np

#Load sentiment analysis model once
sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

#Added a multi-class emotion detection model for future use.
emotion_analyzer = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=1 )

def analyze_sentiment(text, threshold=0.7):
    try:
        result = sentiment_analyzer(text[:512])[0]
        label = result['label'].lower() #positive or negative
        score = result['score']

        if score < threshold:
            return 'neutral' # confidence is too low bhai.
        return label
    except Exception as e:
        print(f"Sentiment analysis failed: {e}")
        return 'neutral' #or we can return none/ raise a custom exception.
    
def detect_emotion(text, threshold=0.5):
    try:
        result = emotion_analyzer(text[:512])[0][0]
        emotion = result['label'].lower()
        score = result['score']
        if score < threshold:
            return 'neutral' # confidence is too low bhai.
        return emotion
    except Exception as e:
        print(f"Emotion Detection Error: {e}")
        return 'neutral'


class RAGSystem:
    def __init__(self, db_connection):
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        #add caching- initialize SQLite cache
        self.cache = SQLiteCache(database_path=".rag_cache.db")

        # Initialize LLM 
        self.llm_deterministic = HuggingFacePipeline.from_model_id(
            model_id="google/flan-t5-base",
            task="text2text-generation",
            device = None,
            model_kwargs={
                "do_sample": False, 
                "max_length": 512, 
                "device_map":"auto"} #for automatic device placement
        )

        self.llm_stochastic = HuggingFacePipeline.from_model_id(
            model_id="google/flan-t5-base",
            task="text2text-generation",
            device = None,
            model_kwargs={
                "do_sample": True,
                "temperature": 0.2, 
                "max_length": 512, 
                "device_map":"auto"} #for automatic device placement
        )
        
        # Connect to ChromaDB (persistent storage)
        self.vector_store = Chroma(
            collection_name="travel_data",
            embedding_function=self.embeddings,
            persist_directory="./chroma_db"
        )
        
        # Link with database connection(SQLAlchemy db object)
        self.db = db_connection

        #Conditional data loading
        #Check if the vector store collection seems empty before loading
        try:
            current_count = self.vector_store._collection.count()
            print(f"Vector store current document count: {current_count}")
            if current_count == 0:
                print("Vector store appears empty. Performing initial data laod..")
                self._load_faqs_into_vectorstore()
                self._load_reviews_into_vectorstore()
                print("Initial data loading complete.")
            else:
                print("Vector store already contains data. Skipping bulk load.")
        except Exception as e:
            print(f"Error checking vector store count or performing initial load: {e}")
            print("Please ensure './chroma_db' is accessible and correctly initialized ")
        print("RAG sustem intialized.")

    def _load_faqs_into_vectorstore(self):
        """Load FAQs from SQL database into Chroma vector store"""
        try:
            print("Attempting to load FAQs from database....")
            faqs = self.db.session.query(FAQ).all() #database interaction
            if not faqs:
                print("No FAQs found in the database to load.")
                return
            documents = [
                f"Question: {faq.question}\nAnswer: {faq.answer}" 
                for faq in faqs] #creates text documents for embedding
            #generate unique ids for chromadb based on FAQ primary key.
            ids=[f"faq_{faq.id}" for faq in faqs]
            #Metadata generation which can helpful for filtering later.
            metadatas = [
                {
                    "source": "faq", 
                    "db_id": faq.id, 
                    "hotel_id":faq.hotel_id
                } 
                for faq in faqs
            ] 
            if documents:
                #Adding to Vector Store
                self.vector_store.add_texts(texts=documents, metadatas=metadatas, ids=ids)
                #save the changes to the persistent chromadb storage.
                self.vector_store.persist()
                print(f"Loaded {len(faqs)} FAQs into vector store.")
            else:
                print("No valid documents generated to load")

        except Exception as e:
            print(f"Error loading FAQs into vector store:{e}")
    def _load_reviews_into_vectorstore(self):
        """Load all reviews from SQL database into ChromaDB"""
        try:
            print("Attempting to load Reviews from database...")    
            reviews = self.db.session.query(Review).all()
            if not reviews:
                print("No Reviews found in the database to load")
                return
            documents = [
                f"Review: {review.content}"
                for review in reviews
            ]
            #Generate unique ids for chromadb based Review Primary key.
            ids = [f"review_{review.id}" for review in reviews]
            metadatas = [
                {
                    "source": "review",
                    "db_id" : review.id,
                    "user_id": review.user_id,
                    "hotel_id": review.hotel_id
                }
                for review in reviews
            ]
            if documents:       
                self.vector_store.add_texts(texts=documents, metadatas=metadatas, ids=ids)
                self.vector_store.persist()
                print(f"Loaded {len(reviews)} Reviews into vector store.")
            else:
                print("No valid Review documents generated to load.")
        except Exception as e:
            print(f"Error loading Reviews into vector store: {e}") 

    def add_faq_to_vectorstore(self, faq:FAQ):
        """Incrementally add a single faq to the vector store"""
        try:
            document = f"Question: {faq.question}\nAnswer: {faq.answer}"
            faq_id = f"faq_{faq.id}" #for consistent id format
            metadata = {"source": "faq", "db_id": faq.id, "hotel_id":faq.hotel_id}
            self.vector_store.add_texts(texts=[document], metadatas=[metadata], ids=[faq_id])
            self.vector_store.persist()
            print(f"Added/updated FAQ {faq.id} in vector store.")
        except Exception as e:
            print(f"Error adding FAQ {faq.id} to vector store: {e}")

    def add_review_to_vectorstore(self, review):
        """Incrementally add a single review to the vector store"""
        try:
            document = f"Review: {review.content}"
            #use consistent id formatfor potential updates  
            review_id = f"review_{review.id}"                             
            metadata = {"source": "review", "db_id": review.id, "user_id": review.user_id, "hotel_id":review.hotel_id}
            self.vector_store.add_texts(texts=[document], metadatas=[metadata], ids=[review_id])
            self.vector_store.persist()
            print(f"Added Review {review.id} in vector store.") 
        except Exception as e:
            print(f"Error adding Review {review.id} to vector store: {e}")

    def get_retriever(self, k: int = 3, score_threshold: float=0.7, filter_dict: dict = None):
        """Create a LangChain retriever with specified search parameters."""
        search_kwargs = {'k':k}
        if score_threshold is not None:
            search_kwargs['score_threshold'] = score_threshold
        if filter_dict is not None:
            search_kwargs['filter'] = filter_dict
           
        return self.vector_store.as_retriever(
            search_kwargs=search_kwargs, search_type="similarity_score_threshold"
        )

    def query_system(self, question: str, role: str="customer"):
        """Full RAG pipeline using LangChain Expression Language(LCEL)
        to handle custom prompts based on user role and return sources"""
        # Load both FAQs and Reviews. Use full methods during query initialization.
        #self._load_faqs_into_vectorstore()
        #self._load_reviews_into_vectorstore()
        #commented out the data loading calls here.
        
        # based on role routing query to correct pipeline.
        if role == "property_owner":
            llm_for_query = self.llm_deterministic
        else:
            llm_for_query = self.llm_stochastic
        # modify retriever for owners to focus on reviews
        if role=="property_owner":
            retriever=self.get_retriever(k=5, filter_dict={"source":"review"})
        else:
            retriever=self.get_retriever(k=3)    
        
        # Customize prompt based on user role
        if role == "property_owner":
            template = """
            You are an expert travel business advisor analyzing a query from a property owner. 
            The context provided below contains exclusively customer reviews about your property.
            Carefully analyze these reviews to extract key feedback, recurring themes, and actionable insights that can help improve your property’s performance.
            Use only the information provided in the context to base your analysis.
            
            Context: {context}
            
            Question: {question}
            
            Answer:
            """
        else:
            template = """
            You are a friendly and knowledgeable travel assistant. 
            The context provided below includes both frequently asked questions and customer reviews related to the query.
            Based solely on this context, provide a clear, concise, and helpful answer that addresses the customer's question. 
            Ensure your response is supportive and actionable, highlighting relevant details from the context.
            
            Context: {context}
            
            Question: {question}
            
            Helpful Answer:
            """
        prompt = PromptTemplate(
            template = template,
            input_variables=["context", "question"]
        )
        #RAG Chain using LCEL.
        #helper function to format retrieved documents into a single context string. 
        def format_docs(docs: list[Document]) -> str:
            if not docs:
                return "No relevant documents found."
            return "\n\n".join(doc.page_content for doc in docs)

        #Define the core chain that generates the answer string.
        rag_chain_core = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()} #pass the input to the next runnable or chain without any modification.
            | prompt            # Feed context and question to the prompt
            | llm_for_query          # Send formatted prompt to LLM
            | StrOutputParser() # Get string output from LLM
        )
        #Define a parallel chain to retrieve source documents alonside the answer.
        rag_chain_with_source = RunnableParallel(
            #retrieve documents first, pass them along as 'docs'
            {"docs": retriever, "question": RunnablePassthrough()}
        ) | RunnableParallel(
            #run the core chain using retrieved docs and question and pass the raw 'docs' through to the final output.
            {"answer": rag_chain_core, "documents": lambda x: x["docs"]}
        )

        #Invoke the chain
        try:
            result  =  rag_chain_with_source.invoke(question)
        except Exception as e:
            return {
                "answer": "Sorry, an error occured while processing your request.",
                "sources": []
            }
        #format and return the output.
        answer = result.get("answer","Sorry, couldn't generate an answer")
        sources_metadata = []
        if "documents" in result and isinstance(result["documents"], list):
            sources_metadata = [
                { "source": doc.metadata.get("source", "unknown"), "db_id": doc.metadata.get("db_id", "N/A")}
                for doc in result["documents"]
            ]
        return {
            "answer" : answer,
            "sources": sources_metadata
        }