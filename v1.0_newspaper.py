from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
from pyppeteer import launch
import asyncio
import json
import os
import re

os.environ["PYPPETEER_CHROMIUM_REVISION"] = "none"
os.environ["PYPPETEER_DOWNLOADS_FOLDER"] = "none"
os.environ["PYPPETEER_BROWSER_EXECUTABLE"] = r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"

class BaseScraper(ABC):
    """Base class for web scrapers."""
    
    def __init__(self, base_url):
        self.base_url = base_url
    
    @abstractmethod
    def get_article_links(self, search_query):
        pass
    
    @abstractmethod
    def extract_article_data(self, url):
        pass

class ElUniversalScraper(BaseScraper):
    """Scraper for El Universal."""

    HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "es-419,es;q=0.9,es-ES;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5,es-MX;q=0.4",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
    }
    
    async def get_article_links(self, search_query):
        search_url = f"{self.base_url}/buscador/?query={search_query}"
        print(search_url)
        browser = None
        all_links = []
        try:
            browser = await launch(
                executablePath=os.environ["PYPPETEER_BROWSER_EXECUTABLE"],
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.newPage()
            await page.goto(search_url, timeout=90000)

            result = await page.content()
            soup = BeautifulSoup(result, 'html.parser')
            
            pages = soup.find('div', class_="result_count")
            if not pages:
                print("Could not find count result div")
                return []
                
            result_text = pages.get_text()
            match = re.search(r'(\d+)', result_text)
            if not match:
                print("No se encontró el número de resultados en la búsqueda.")
                return []
                
            result_number = int(match.group(1))
            each_page_results = 20
            #next_pages = max(1, round(result_number / each_page_results))
            next_pages = 5
            print(f"Found {result_number} results across {next_pages} pages")
            print("Reading page 1")
            links = soup.find_all('a', href=True, onmousedown=True)
            all_links.extend([self.base_url + link['href'] for link in links])

            if next_pages > 1:
                for _ in range(next_pages - 1): 
                    print(f"Reading page {_+2}") 
                    try:
                        next_button = await page.querySelector("a.next_btn")
                        if not next_button:
                            print("No next button found")
                            break

                        is_visible = await page.evaluate('(element) => element.offsetParent !== null', next_button)
                        if not is_visible:
                            print("Next button is not visible")
                            break
                        
                        await next_button.click()
                        await page.waitForSelector("a.next_btn", {'timeout': 120000})  
                        await asyncio.sleep(3)

                        content = await page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        links = soup.find_all('a', href=True, onmousedown=True)
                        all_links.extend([self.base_url + link['href'] for link in links])
                        
                    except Exception as e:
                        print(f"Error processing page: {str(e)}")
                        break

        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            return []
            
        finally:
            if browser:
                await browser.close()
                
        return all_links
    
    def extract_article_data(self, article_url):
        response = requests.get(article_url)
        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", id="fusion-metadata")
        data = ElUniversalScraper.get_page_keys(script_tag)
        
        full_description = " ".join(
            [tag.get_text(separator=" ", strip=True) for tag in soup.find_all("p", {"itemprop": "description", "class": "sc__font-paragraph"})]
        )
        
        return data, full_description
    
    def get_page_keys(script_tag):
        if not script_tag:
            return {}
        match = re.search(r'Fusion\.globalContent\s*=\s*(\{.*?\})\s*;', script_tag.string.strip(), re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return {}
        return {}

class LaJornadaScraper(BaseScraper):
    """Scraper for La Jornada."""
    
    def get_article_links(self, search_query):
        search_url = f"{self.base_url}/busqueda/{search_query}"
        response = requests.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        return [a['href'] for a in soup.select('.resultado-busqueda a')]
    
    def extract_article_data(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1').text.strip()
        content = ' '.join(p.text for p in soup.find_all('p'))
        return {'title': title, 'content': content}

class ReformaScraper(BaseScraper):
    """Scraper for Reforma."""
    
    def get_article_links(self, search_query):
        search_url = f"{self.base_url}/resultados?q={search_query}"
        response = requests.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        return [a['href'] for a in soup.select('article a')]
    
    def extract_article_data(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1').text.strip()
        content = ' '.join(p.text for p in soup.find_all('p'))
        return {'title': title, 'content': content}

class DynamicScraper:
    """Handles dynamic content loading with pyppeteer."""
    
    async def get_dynamic_content(self, url):
        browser = await launch()
        page = await browser.newPage()
        await page.goto(url, {'waitUntil': 'networkidle2'})
        content = await page.content()
        await browser.close()
        return content

class WebScraper:
    """Main class to manage scraping across different news sites."""
    
    def __init__(self, output_file="V1.0_articles.json"):
        self.scrapers = {
            'el_universal': ElUniversalScraper('https://www.eluniversal.com.mx'),
            'la_jornada': LaJornadaScraper('https://www.jornada.com.mx'),
            'reforma': ReformaScraper('https://www.reforma.com')
        }
        self.output_file = output_file
    
    async def scrape(self, site, query):
        scraper = self.scrapers.get(site)
        if not scraper:
            raise ValueError(f"No scraper found for {site}")
        
        links = await scraper.get_article_links(query)
        articles = []
        
        for link in links:
            try:
                articles.append(scraper.extract_article_data(link))
            except Exception as e:
                print(f"Error processing article {link}: {e}")
        
        with open(self.output_file, "w", encoding="utf-8") as file:
            json.dump(articles, file, indent=4, ensure_ascii=False)
        
        return articles

if __name__ == "__main__":
    ws = WebScraper()
    
    # Lista de periódicos a buscar
    newspapers = [
        'el_universal'#,
        #'reforma',
        #'la_jornada'
    ]
    
    # Lista de términos de búsqueda
    search_terms = [
        'feminicidio',
        'violencia+de+género'
    ]
    
    all_results = {}
    
    # Realizar búsqueda para cada periódico y término
    for newspaper in newspapers:
        print(f"\n=== Buscando en {newspaper.replace('_', ' ').title()} ===")
        all_results[newspaper] = {}
        
        for term in search_terms:
            try:
                print(f"\nBuscando artículos sobre: {term}")
                results = asyncio.run(ws.scrape(newspaper, term))
                
                if results is not None:
                    all_results[newspaper][term] = results
                    print(f"Se encontraron {len(results)} artículos para '{term}'")
                else:
                    print(f"No se obtuvieron resultados para '{term}'")
                    all_results[newspaper][term] = []
                    
            except Exception as e:
                print(f"Error al procesar '{term}' en {newspaper}: {str(e)}")
                all_results[newspaper][term] = []
    
    # Imprimir resumen total
    print("\n====== RESUMEN TOTAL ======")
    grand_total = 0
    
    for newspaper in newspapers:
        newspaper_total = sum(len(articles) for articles in all_results[newspaper].values())
        grand_total += newspaper_total
        print(f"\n{newspaper.replace('_', ' ').title()}:")
        print(f"Total de artículos: {newspaper_total}")
        
        for term, articles in all_results[newspaper].items():
            print(f"- {term}: {len(articles)} artículos")
    
    print(f"\nTotal general de artículos encontrados: {grand_total}")
    print(f"Todos los artículos han sido guardados en {ws.output_file}")