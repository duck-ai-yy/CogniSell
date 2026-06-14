import os
from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Optional, List

load_dotenv()

# Extended schema for CRM
class EnrichedCRMInfo(BaseModel):
    name: Optional[str] = Field(description="The person's name")
    company: Optional[str] = Field(description="The company name")
    title: Optional[str] = Field(description="The person's title or position")
    phone: Optional[str] = Field(description="Phone number")
    email: Optional[str] = Field(description="Email address")
    company_website: Optional[str] = Field(description="Company website URL")
    social_media_person: Optional[List[str]] = Field(default_factory=list, description="Links to the person's social media (e.g. LinkedIn, Twitter)")
    social_media_company: Optional[List[str]] = Field(default_factory=list, description="Links to the company's social media (e.g. LinkedIn, Twitter)")
    company_news_events: Optional[List[str]] = Field(default_factory=list, description="Recent major news or events related to the company or person")
    other_crm_info: Optional[str] = Field(description="Any other useful CRM context found (e.g. company size, industry, location, recent acquisitions)")

def enrich_business_card_data(basic_info: dict) -> dict:
    """
    Takes basic business card info, searches the internet via Tavily, 
    and synthesizes an EnrichedCRMInfo object using Gemini.
    """
    # Instantiate Tavily client
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_api_key:
        print("WARNING: TAVILY_API_KEY not found in .env. Skipping internet research.")
        return basic_info

    tavily_client = TavilyClient(api_key=tavily_api_key)
    
    person_name = basic_info.get("name", "")
    company_name = basic_info.get("company", "")
    
    if not person_name and not company_name:
        return basic_info
        
    search_queries = []
    if company_name:
        search_queries.append(f"{company_name} company news events")
        search_queries.append(f"{company_name} official website linkedin twitter")
    if person_name and company_name:
        search_queries.append(f"{person_name} {company_name} linkedin profile")

    search_contexts = []
    
    # Execute searches
    for query in search_queries:
        try:
            print(f"  -> Tavily searching: '{query}'")
            response = tavily_client.search(query, search_depth="basic", max_results=3)
            results = response.get("results", [])
            for res in results:
                content = res.get("content", "")
                url = res.get("url", "")
                search_contexts.append(f"Source: {url}\nContent: {content}\n")
        except Exception as e:
            print(f"  -> Error searching Tavily for '{query}': {e}")
            
    combined_context = "\n".join(search_contexts)
    
    # Synthesize with Gemini
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    parser = PydanticOutputParser(pydantic_object=EnrichedCRMInfo)
    
    prompt = PromptTemplate(
        template="""You are a CRM data enrichment assistant. 
You have been given basic information extracted from a business card, along with web search results about the person and company.
Combine the basic information with the web search results to produce a comprehensive, enriched CRM profile.

Basic Information from Business Card:
{basic_info}

Web Search Results:
{search_results}

Fill out the fields as completely and accurately as possible based on the available data.
If you cannot find specific information in the search results or basic info, leave it as null or an empty list.

{format_instructions}""",
        input_variables=["basic_info", "search_results"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    chain = prompt | llm | parser
    
    try:
        enriched_result = chain.invoke({
            "basic_info": str(basic_info),
            "search_results": combined_context
        })
        return enriched_result.model_dump()
    except Exception as e:
        print(f"  -> Error synthesizing research with Gemini: {e}")
        return basic_info
