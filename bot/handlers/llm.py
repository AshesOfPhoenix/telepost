from langchain.embeddings.base import Embeddings
from langchain.llms.base import BaseLLM
from langchain.tools.base import BaseTool
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from dotenv import load_dotenv

load_dotenv()

import os 

OLLAMA_BASE_URLS = os.getenv("OLLAMA_BASE_URLS", "localhost:11434")

def get_llm(llmname) -> BaseLLM:
    """Function to get the LLM. Replace with your desired LLM."""
    if llmname == "gpt-4o-mini":
        return ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    if llmname == "llama3.1":
        return ChatOllama(
            model="llama3.1",
            temperature=0,
            base_url=OLLAMA_BASE_URLS,
            # other params...
        )

def get_embeddings(embeddingmodel) -> Embeddings:
    """Function to get the embeddings model. Replace with your desired embeddings."""
    if embeddingmodel == "openai":
        return OpenAIEmbeddings()
    if embeddingmodel == "ollama":
        embed = OllamaEmbeddings(
            model="llama3",
            base_url=OLLAMA_BASE_URLS,
            
        )
        return embed

# Initialize components
# llm = get_llm('llama3.1')
llm = get_llm('gpt-4o-mini')
# embeddings = get_embeddings('ollama')
embeddings = get_embeddings('openai')