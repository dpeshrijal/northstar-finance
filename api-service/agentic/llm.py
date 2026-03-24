from openai import AzureOpenAI
from .config import settings


client = AzureOpenAI(
    api_version=settings.aoai_api_version,
    azure_endpoint=settings.aoai_endpoint,
    api_key=settings.aoai_key,
)
