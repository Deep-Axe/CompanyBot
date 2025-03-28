import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import pandas as pd
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime
from urllib.parse import urlparse, quote_plus
import yfinance as yf
import tweepy
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(
    base_url="https://router.huggingface.co/novita/v3/openai",
    api_key="hf_**********************************" 
    #get api_key from hugging face
)

# Streamlit UI setup
st.set_page_config(page_title="Company Intelligence Bot", layout="wide")
st.title("Company Intelligence Bot")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "company_data" not in st.session_state:
    st.session_state.company_data = {}
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "current_input" not in st.session_state:
    st.session_state.current_input = ""
if "awaiting_response" not in st.session_state:
    st.session_state.awaiting_response = False
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "data_sources" not in st.session_state:
    st.session_state.data_sources = []
if "financial_data" not in st.session_state:
    st.session_state.financial_data = None
if "company_logo" not in st.session_state:
    st.session_state.company_logo = None
if "last_update" not in st.session_state:
    st.session_state.last_update = None

# Sidebar for company selection and data fetching
st.sidebar.header("Company Research")
company_name = st.sidebar.text_input("Company Name", "Tesla")
company_domain = st.sidebar.text_input("Company Domain (Optional)", "")
ticker_symbol = st.sidebar.text_input("Stock Ticker Symbol (Optional)", "")

# Web scraping and data collection functions
def fetch_company_website(company_name, domain=None):
    """Find the official website for a company"""
    if domain and (domain.startswith('http://') or domain.startswith('https://')):
        return domain
    
    if domain:
        if not domain.startswith('http'):
            return f"https://{domain}"
        return domain
        
    search_url = f"https://www.google.com/search?q={quote_plus(company_name)} official website"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for the first organic result
        for div in soup.find_all('div'):
            for a in div.find_all('a'):
                href = a.get('href', '')
                if 'url=' in href and 'google' not in href:
                    url_match = re.search(r'url\?q=([^&]+)', href)
                    if url_match:
                        url = url_match.group(1)
                        if url.startswith('http') and 'google.com' not in url:
                            return url
    except Exception as e:
        st.sidebar.error(f"Error fetching website: {e}")
    return None

def fetch_logo(company_name, website_url):
    """Try to find company logo"""
    try:
        if website_url:
            # Try to get favicon
            parsed_url = urlparse(website_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            favicon_url = f"{base_url}/favicon.ico"
            
            response = requests.get(favicon_url, stream=True, timeout=5)
            if response.status_code == 200:
                return favicon_url
        
        # If favicon not found, search for logo
        search_url = f"https://www.google.com/search?q={quote_plus(company_name)} logo&tbm=isch"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find image tags
        img_tags = soup.find_all('img')
        for img in img_tags:
            if img.get('src') and img.get('src').startswith('http') and 'gstatic' not in img.get('src'):
                return img.get('src')
    except:
        pass
    
    return None

def scrape_website_content(url, max_chars=100000):
    """Extract content from a webpage"""
    if not url:
        return ""
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        # Extract text
        text = soup.get_text(separator=' ', strip=True)
        
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:max_chars]
    except Exception as e:
        st.sidebar.warning(f"Error scraping {url}: {e}")
        return ""

def fetch_google_news(company):
    """Fetch news about the company from Google"""
    search_url = f"https://www.google.com/search?q={quote_plus(company)}+news&tbm=nws"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        news_items = []
        results = soup.find_all("div", {"class": re.compile("^[a-zA-Z]")})
        
        for result in results:
            headline_elem = result.find("h3")
            if headline_elem:
                headline = headline_elem.text
                snippet_elem = result.find(["div", "span"], {"class": re.compile("^[a-zA-Z]")})
                snippet = snippet_elem.text if snippet_elem else ""
                if len(headline) > 10:  # Avoid empty or tiny headlines
                    news_items.append(f"Headline: {headline}\nSnippet: {snippet}")
                
        return "\n\n".join(news_items[:10])
    except Exception as e:
        return f"Error fetching Google News: {str(e)}"

def fetch_linkedin_info(company):
    """Attempt to fetch information from LinkedIn via Google search"""
    search_url = f"https://www.google.com/search?q=site:linkedin.com+{quote_plus(company)}+company"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = soup.find_all("div")
        linkedin_info = []
        linkedin_url = None
        
        for result in results:
            links = result.find_all("a")
            for link in links:
                href = link.get("href", "")
                if "linkedin.com/company" in href:
                    url_match = re.search(r'url\?q=([^&]+)', href)
                    if url_match:
                        linkedin_url = url_match.group(1)
                        break
            
            title_elem = result.find("h3")
            if title_elem and "LinkedIn" in title_elem.text:
                snippet_elem = result.find(["div", "span"], {"class": re.compile("^[a-zA-Z]")})
                if snippet_elem and len(snippet_elem.text) > 30:
                    linkedin_info.append(f"LinkedIn Info: {snippet_elem.text}")
        
        if linkedin_url:
            linkedin_info.insert(0, f"LinkedIn Company URL: {linkedin_url}")
                
        return "\n\n".join(linkedin_info[:5])
    except Exception as e:
        return f"Error fetching LinkedIn information: {str(e)}"

def fetch_twitter_info(company_name):
    """Fetch Twitter information about the company using Google search"""
    search_url = f"https://www.google.com/search?q=site:twitter.com+{quote_plus(company_name)}+official"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = soup.find_all("div")
        twitter_info = []
        twitter_handle = None
        
        for result in results:
            links = result.find_all("a")
            for link in links:
                href = link.get("href", "")
                if "twitter.com/" in href and not "search?" in href:
                    url_match = re.search(r'url\?q=([^&]+)', href)
                    if url_match:
                        twitter_url = url_match.group(1)
                        handle_match = re.search(r'twitter\.com/([^/]+)', twitter_url)
                        if handle_match:
                            twitter_handle = handle_match.group(1)
                            break
            
            title_elem = result.find("h3")
            if title_elem and "Twitter" in title_elem.text:
                snippet_elem = result.find(["div", "span"], {"class": re.compile("^[a-zA-Z]")})
                if snippet_elem and len(snippet_elem.text) > 20:
                    twitter_info.append(f"Twitter Info: {snippet_elem.text}")
        
        if twitter_handle:
            twitter_info.insert(0, f"Twitter Handle: @{twitter_handle}")
                
        return "\n\n".join(twitter_info[:5])
    except Exception as e:
        return f"Error fetching Twitter information: {str(e)}"

def fetch_company_reviews(company):
    """Fetch company reviews from Google"""
    search_url = f"https://www.google.com/search?q={quote_plus(company)}+reviews+glassdoor+indeed"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        review_snippets = []
        results = soup.find_all("div")
        
        for result in results:
            snippet_elem = result.find(["div", "span"], {"class": re.compile("^[a-zA-Z]")})
            if snippet_elem and "review" in snippet_elem.text.lower() and len(snippet_elem.text) > 50:
                review_snippets.append(snippet_elem.text)
                
        return "\n\n".join(review_snippets[:5])
    except Exception as e:
        return f"Error fetching company reviews: {str(e)}"

def fetch_financial_data(ticker):
    """Fetch financial data if ticker symbol is provided"""
    if not ticker:
        return None
        
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or len(info) < 5: 
            return None
            
        hist = stock.history(period="1y")
        
        if hist.empty:
            return None
            
        financial_data = {
            "info": {k: v for k, v in info.items() if not isinstance(v, dict) and not isinstance(v, list)},
            "history": hist
        }
        
        return financial_data
    except:
        return None

def collect_company_data(company_name, company_domain="", ticker_symbol=""):
    """Collect data about a company from multiple sources"""
    data = {}
    data_sources = []
    
    with st.sidebar.status("Finding company website..."):
        website_url = fetch_company_website(company_name, company_domain)
        if website_url:
            data["website_url"] = website_url
            st.sidebar.write(f"Website: {website_url}")
            
            with st.sidebar.status("Extracting website content..."):
                website_content = scrape_website_content(website_url)
                if website_content:
                    data["website_content"] = website_content
                    data_sources.append(f"COMPANY WEBSITE CONTENT:\n{website_content[:2000]}...[truncated]")
    
    with st.sidebar.status("Finding company logo..."):
        logo_url = fetch_logo(company_name, website_url if "website_url" in data else None)
        if logo_url:
            data["logo_url"] = logo_url
    
    with st.sidebar.status("Collecting news articles..."):
        news_content = fetch_google_news(company_name)
        if news_content:
            data["news"] = news_content
            data_sources.append(f"RECENT NEWS ABOUT {company_name.upper()}:\n{news_content}")
    
    with st.sidebar.status("Finding LinkedIn information..."):
        linkedin_info = fetch_linkedin_info(company_name)
        if linkedin_info:
            data["linkedin"] = linkedin_info
            data_sources.append(f"LINKEDIN INFORMATION ABOUT {company_name.upper()}:\n{linkedin_info}")
    
    with st.sidebar.status("Finding Twitter information..."):
        twitter_info = fetch_twitter_info(company_name)
        if twitter_info:
            data["twitter"] = twitter_info
            data_sources.append(f"TWITTER INFORMATION ABOUT {company_name.upper()}:\n{twitter_info}")
    
    with st.sidebar.status("Finding company reviews..."):
        reviews = fetch_company_reviews(company_name)
        if reviews:
            data["reviews"] = reviews
            data_sources.append(f"COMPANY REVIEWS FOR {company_name.upper()}:\n{reviews}")
    
    if ticker_symbol:
        with st.sidebar.status(f"Fetching financial data for {ticker_symbol}..."):
            financial_data = fetch_financial_data(ticker_symbol)
            if financial_data:
                data["financial"] = financial_data
                financial_summary = f"Market Cap: ${financial_data['info'].get('marketCap', 'N/A')}\n"
                financial_summary += f"Industry: {financial_data['info'].get('industry', 'N/A')}\n"
                financial_summary += f"Employees: {financial_data['info'].get('fullTimeEmployees', 'N/A')}\n"
                financial_summary += f"Revenue: ${financial_data['info'].get('totalRevenue', 'N/A')}"
                data_sources.append(f"FINANCIAL DATA FOR {company_name.upper()} ({ticker_symbol}):\n{financial_summary}")
    
    summary = f"Data collected about {company_name}:\n"
    if "website_content" in data:
        summary += "✅ Company Website Content\n"
    if "news" in data:
        summary += "✅ Recent News Articles\n"
    if "linkedin" in data:
        summary += "✅ LinkedIn Information\n"
    if "twitter" in data:
        summary += "✅ Twitter Information\n"
    if "reviews" in data:
        summary += "✅ Company Reviews\n"
    if "financial" in data:
        summary += f"✅ Financial Data (Ticker: {ticker_symbol})\n"
    
    data["summary"] = summary
    data["data_sources"] = data_sources
    data["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return data

def create_combined_text(company_data):
    """Create combined text from all data sources"""
    combined = []
    
    if "data_sources" in company_data:
        combined = company_data["data_sources"]
    
    full_text = "\n\n" + "-"*50 + "\n\n".join(combined)
    return full_text

def generate_company_summary(company_name, company_data):
    """Generate an AI summary of the company based on collected data"""
    if not company_data:
        return "No data available to generate summary."
    
    combined_text = create_combined_text(company_data)
    
    try:
        system_message = f"""You are a business intelligence analyst. 
        Create a concise but comprehensive summary of {company_name} based on the information provided.
        Include what the company does, key products/services, market position, and any other notable information.
        Keep your summary to 3-4 paragraphs maximum.
        Only use information from the provided data.
        """
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Here is the collected data about {company_name}. Please summarize it:\n{combined_text[:30000]}"}
        ]
        
        completion = client.chat.completions.create(
            model="deepseek/deepseek-v3-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.3,
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error generating summary: {str(e)}"

col1, col2 = st.sidebar.columns([1, 1])
with col1:
    fetch_button = st.button("Research Company", use_container_width=True)
with col2:
    clear_button = st.button("Clear Data", use_container_width=True)

if clear_button:
    st.session_state.company_data = {}
    st.session_state.data_sources = []
    st.session_state.summary = ""
    st.session_state.chat_history = []
    st.session_state.financial_data = None
    st.session_state.company_logo = None
    st.session_state.last_update = None
    st.session_state.awaiting_response = False
    st.experimental_rerun()

if fetch_button:
    with st.spinner(f"Researching {company_name}..."):
        st.session_state.company_data = collect_company_data(company_name, company_domain, ticker_symbol)
        
        if "data_sources" in st.session_state.company_data:
            st.session_state.data_sources = st.session_state.company_data["data_sources"]
        
        if "summary" in st.session_state.company_data:
            st.session_state.summary = st.session_state.company_data["summary"]
        
        if "financial" in st.session_state.company_data:
            st.session_state.financial_data = st.session_state.company_data["financial"]
        
        if "logo_url" in st.session_state.company_data:
            st.session_state.company_logo = st.session_state.company_data["logo_url"]
        
        if "last_update" in st.session_state.company_data:
            st.session_state.last_update = st.session_state.company_data["last_update"]
        
        ai_summary = generate_company_summary(company_name, st.session_state.company_data)
        st.session_state.ai_summary = ai_summary
        
        st.success(f"Research complete for {company_name}!")

if st.session_state.company_data:
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.session_state.company_logo:
            try:
                st.image(st.session_state.company_logo, width=100)
            except:
                st.image("https://via.placeholder.com/100x100?text=Logo", width=100)
        else:
            st.image("https://via.placeholder.com/100x100?text=No+Logo", width=100)
    
    with col2:
        st.header(company_name)
        if "website_url" in st.session_state.company_data:
            st.write(f"🌐 [Company Website]({st.session_state.company_data['website_url']})")
        
        if st.session_state.last_update:
            st.caption(f"Last updated: {st.session_state.last_update}")
    
    if "ai_summary" in st.session_state:
        st.subheader("Company Overview")
        st.info(st.session_state.ai_summary)
    else:
        st.info(st.session_state.summary)
    
    tabs = st.tabs(["Company Information", "News", "Financial Data", "Social Media"])
    
    with tabs[0]:
        if "website_content" in st.session_state.company_data:
            with st.expander("Website Content", expanded=False):
                st.markdown(st.session_state.company_data["website_content"][:5000])
                if len(st.session_state.company_data["website_content"]) > 5000:
                    st.caption("Content truncated for display. Full content used for answering questions.")
        
        if "reviews" in st.session_state.company_data:
            with st.expander("Company Reviews", expanded=True):
                st.markdown(st.session_state.company_data["reviews"])
    
    with tabs[1]:
        if "news" in st.session_state.company_data:
            st.markdown(st.session_state.company_data["news"])
        else:
            st.write("No news information available.")
    
    with tabs[2]:
        if st.session_state.financial_data:
            fin_info = st.session_state.financial_data["info"]
            
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            
            with metrics_col1:
                if "marketCap" in fin_info:
                    market_cap = fin_info["marketCap"]
                    if market_cap > 1_000_000_000:
                        market_cap_str = f"${market_cap/1_000_000_000:.2f}B"
                    elif market_cap > 1_000_000:
                        market_cap_str = f"${market_cap/1_000_000:.2f}M"
                    else:
                        market_cap_str = f"${market_cap:,.0f}"
                    st.metric("Market Cap", market_cap_str)
                
                if "sector" in fin_info:
                    st.metric("Sector", fin_info["sector"])
            
            with metrics_col2:
                if "currentPrice" in fin_info:
                    st.metric("Current Price", f"${fin_info['currentPrice']:.2f}")
                
                if "industry" in fin_info:
                    st.metric("Industry", fin_info["industry"])
            
            with metrics_col3:
                if "fullTimeEmployees" in fin_info:
                    employees = fin_info["fullTimeEmployees"]
                    if employees is not None:
                        st.metric("Employees", f"{employees:,}")
                
                if "website" in fin_info:
                    st.write(f"🌐 [Yahoo Finance](https://finance.yahoo.com/quote/{ticker_symbol})")
            
            # Stock chart
            if "history" in st.session_state.financial_data:
                hist = st.session_state.financial_data["history"]
                if not hist.empty:
                    st.subheader("Stock Price - Last 12 Months")
                    fig, ax = plt.subplots(figsize=(10, 6))
                    ax.plot(hist.index, hist['Close'])
                    ax.set_xlabel('Date')
                    ax.set_ylabel('Price ($)')
                    ax.grid(True)
                    st.pyplot(fig)
        else:
            if ticker_symbol:
                st.write(f"No financial data available for ticker: {ticker_symbol}")
            else:
                st.write("No ticker symbol provided for financial data.")
    
    with tabs[3]:
        social_col1, social_col2 = st.columns(2)
        
        with social_col1:
            st.subheader("LinkedIn")
            if "linkedin" in st.session_state.company_data:
                st.markdown(st.session_state.company_data["linkedin"])
            else:
                st.write("No LinkedIn information available.")
        
        with social_col2:
            st.subheader("Twitter")
            if "twitter" in st.session_state.company_data:
                st.markdown(st.session_state.company_data["twitter"])
            else:
                st.write("No Twitter information available.")

    st.markdown("---")
    st.subheader("Chat about the Company")
    
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.markdown(f"**You:** {message['content']}")
        else:
            st.markdown(f"**AI:** {message['content']}")
    
    def process_input():
        if st.session_state.user_input and st.session_state.company_data:
            user_question = st.session_state.user_input
            st.session_state.current_input = user_question
            st.session_state.awaiting_response = True
            st.session_state.user_input = ""
            
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            
            # Create combined text from all data sources
            combined_text = create_combined_text(st.session_state.company_data)
            
            system_message = f"""You are a company intelligence assistant for {company_name}.
            Use ONLY the following information to answer questions about {company_name}.
            Be concise, factual, and only use the information provided.
            If you don't know something, admit it rather than making up information.
            
            COMPANY INFORMATION:
            {combined_text[:50000]}
            """
            
            messages = [
                {"role": "system", "content": system_message},
            ]
            
            for msg in st.session_state.chat_history[-8:]: 
                messages.append(msg)
            
            try:
                completion = client.chat.completions.create(
                    model="deepseek/deepseek-v3-turbo",
                    messages=messages,
                    max_tokens=800,
                    temperature=0.5,
                )
                
                ai_response = completion.choices[0].message.content
                
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                
                st.session_state.awaiting_response = False
                st.session_state.current_input = ""
                
            except Exception as e:
                st.error(f"Error generating response: {str(e)}")
                st.session_state.awaiting_response = False
                
        elif st.session_state.user_input:
            st.warning("Please research a company first by clicking the 'Research Company' button.")
            st.session_state.user_input = ""

    user_input = st.text_input("Ask a question about the company:", key="user_input", on_change=process_input)
    
    if st.session_state.awaiting_response:
        with st.spinner("Generating response..."):
            time.sleep(0.1)  
    with st.expander("View Raw Data Sources"):
        if st.session_state.data_sources:
            data_source_tabs = st.tabs([f"Source {i+1}" for i in range(len(st.session_state.data_sources))])
            
            for i, src in enumerate(st.session_state.data_sources):
                with data_source_tabs[i]:
                    st.text(src)
        else:
            st.write("No data sources available.")

else:
    st.info("Enter a company name and click 'Research Company' to begin analyzing company information.")
    
    with st.expander("How to use this tool"):
        st.markdown("""
        ### Instructions:
        1. Enter a company name in the sidebar
        2. Optionally, provide the company domain and stock ticker for more targeted results
        3. Click 'Research Company' to gather information
        4. Once data is collected, you can:
           - Review the AI-generated summary
           - Explore different information tabs
           - Ask questions about the company in the chat interface
        
        ### What data is collected:
        - Company website content
        - Recent news articles
        - LinkedIn and Twitter information
        - Company reviews
        - Financial data (if ticker symbol provided)
        
        ### Sample questions:
        - "What products does this company offer?"
        - "What is their business model?"
        - "What are their recent news mentions?"
        - "What is their market position?"
        - "How many employees do they have?"
        """)

st.markdown("---")
st.caption("This tool collects publicly available information about companies to provide insights. Information may not be 100% accurate or complete.")
