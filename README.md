# Company Intelligence Bot: Report

## Approach
The CompanyBot is built upon reverse-engineered implementations of Cohesive_GPT and Cohesive_Agent, enhancing its ability to retrieve and process company-related insights dynamically. This preliminary website serves as an initial proof-of-concept for ease of understanding, and it can be seamlessly ported to Google Sheets for further integration into existing workflows.

The CompanyBot implements a multi-source data retrieval system combined with a generative AI interface, enabling users to research organizations and ask natural language questions about them. The system employs web scraping to gather information from various online sources, processes this data to extract relevant insights, and provides a conversational interface powered by a large language model (LLM). This approach follows the Retrieval-Augmented Generation (RAG) paradigm, where externally sourced information enhances the model's responses.

## Data Collection Architecture
The system collects information from multiple sources:
- **Company websites**: Automatically detected and scraped for core business information
- **News articles**: Retrieved from Google News to provide recent developments
- **Social media presence**: LinkedIn and Twitter information extracted through search results
- **Company reviews**: Aggregated from platforms like Glassdoor and Indeed
- **Financial data**: Stock market performance and metrics via Yahoo Finance API

The multi-source approach ensures comprehensive coverage while redundancy across sources improves reliability. Data collection processes respect robots.txt directives and implement rate limiting to ensure ethical web scraping.

## Model Selection
The implementation utilizes the DeepSeek-v3-Turbo model accessed through Hugging Face's API router. This model was selected for its:
- Strong performance on analytical business text tasks
- Competitive context window (allowing more data to be processed in a single query)
- Reasonable inference speed for real-time applications
- Cost-effectiveness compared to alternatives with similar capabilities

The model is accessed via a custom endpoint configuration:
```python
client = OpenAI(
    base_url="https://router.huggingface.co/novita/v3/openai",
    api_key="hf_***************************"
)
