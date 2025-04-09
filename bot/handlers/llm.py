from langchain.embeddings.base import Embeddings
from langchain.llms.base import BaseLLM
from langchain.tools.base import BaseTool
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

import os 


def get_llm(llmname) -> BaseLLM:
    """Function to get the LLM. Replace with your desired LLM."""
    if llmname == "gpt-4o-mini":
        return ChatOpenAI(model_name="gpt-4o-mini", temperature=0)


def get_embeddings(embeddingmodel) -> Embeddings:
    """Function to get the embeddings model. Replace with your desired embeddings."""
    if embeddingmodel == "openai":
        return OpenAIEmbeddings()

# Initialize components
# llm = get_llm('llama3.1')
llm = get_llm('gpt-4o-mini')
# embeddings = get_embeddings('ollama')
embeddings = get_embeddings('openai')