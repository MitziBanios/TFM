from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
from pyppeteer import launch
import asyncio
import json
import os
import re
import time
import spacy
from collections import Counter
from datetime import datetime
import locale
import csv
import unicodedata
import tkinter as tk
from tkinter import filedialog
from nltk.corpus import stopwords
import nltk
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


os.environ["PYPPETEER_CHROMIUM_REVISION"] = "none"
os.environ["PYPPETEER_DOWNLOADS_FOLDER"] = "none"
os.environ["PYPPETEER_BROWSER_EXECUTABLE"] = r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

class BaseScraper(ABC):
    """Base class for web scrapers."""
    
    def __init__(self, base_url):
        self.base_url = base_url
    
    @staticmethod
    def cargar_terminos():
        root = tk.Tk()
        root.withdraw()  # Oculta la ventana principal de tkinter
        archivo = filedialog.askopenfilename(
            title="Selección de archivo CSV",  
            filetypes=[("CSV Files", "*.csv")]  # Solo permite archivos CSV
        )
        
        palabras_objetivo = []
        
        if archivo:
            with open(archivo, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Asumimos que la columna 'TERMINOS' contiene las palabras clave
                    if 'TERMINOS' in row:
                        palabras_objetivo.append(row['TERMINOS'].strip().lower())

            return palabras_objetivo
        else:
            print("No se seleccionó ningún archivo.")
            return []
    
    @staticmethod
    def normalizar_fecha(fecha_str):
        fecha_str = fecha_str.strip()
        if fecha_str.endswith("Z"):
            fecha_str = fecha_str.replace("Z", "")

        #Formato ISO
        try:
            fecha = datetime.fromisoformat(fecha_str)
            return fecha.strftime('%d/%m/%Y')
        except ValueError:
            pass

        #Formato tipo "24 de abril de 2025 17:15"
        try:
            fecha_str = re.sub(r'\s+\d{1,2}:\d{2}.*', '', fecha_str)
            fecha = datetime.strptime(fecha_str, "%d de %B de %Y")
            return fecha.strftime('%d/%m/%Y')
        except ValueError:
            pass

        return fecha_str
    
    @staticmethod
    def codigo_pais(country):
        country_clean = ''.join(
            c for c in unicodedata.normalize('NFD', country)
            if unicodedata.category(c) != 'Mn'
        )
        codigo_pais = country_clean[:3].upper()

        return codigo_pais
    
    @staticmethod
    def quitar_acentos(texto):
        return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    
    @staticmethod
    #def word_count(full_description, palabras_objetivo):
    def word_count(full_description):
        texto_normalizado = BaseScraper.quitar_acentos(full_description.lower())

        words = re.findall(r'\b\w+\b', texto_normalizado.lower())
        stop_words = set(stopwords.words('spanish'))# + stopwords.words('english'))
        filtered_words = [word for word in words if word not in stop_words]
        word_counts = Counter(filtered_words)
        
        # Contamos las ocurrencias solo para las palabras de 'palabras_objetivo'
        #conteo_filtrado = {palabra: word_counts.get(palabra, 0) for palabra in palabras_objetivo}

        #return conteo_filtrado
        return word_counts

    nlp = spacy.load("es_core_news_md")

    # Abreviaciones comunes de estados mexicanos
    estado_abrevs = {
        "Mor.": "Morelos", "CDMX": "Ciudad de México", "Edo. Méx.": "Estado de México",
        "Jal.": "Jalisco", "Ver.": "Veracruz", "Sin.": "Sinaloa"
    }

    # Lista de estados válidos (puedes ampliarla)
    estados_mex = set([
        "Morelos", "Ciudad de México", "Jalisco", "Veracruz", "Sinaloa",
        "Puebla", "Oaxaca", "Chiapas", "Michoacán", "Estado de México",
        "Yucatán", "Querétaro", "Nuevo León", "Tamaulipas"
    ])

    # Países válidos
    paises = {
        "México": "México", "Mexico": "México",
        "Estados Unidos": "Estados Unidos", "USA": "Estados Unidos", "EE.UU.": "Estados Unidos"
    }

    state_abbrevs = {
        "MX": {
            "Mor.": "Morelos", "CDMX": "Ciudad de México", "Edo. Méx.": "Estado de México",
            "Jal.": "Jalisco", "Ver.": "Veracruz", "Sin.": "Sinaloa"
        },
        "US": {
            "CA": "California", "NY": "New York", "TX": "Texas", "WA": "Washington"
        }
    }

    states_by_country = {
        "México": ["Morelos", "Ciudad de México", "Estado de México", "Jalisco", "Veracruz",
                   "Sinaloa", "Puebla", "Oaxaca", "Chiapas", "Michoacán", "Yucatán", "Querétaro",
                   "Nuevo León", "Tamaulipas"],
        "Estados Unidos": ["California", "New York", "Texas", "Washington", "Florida", "Illinois"]
    }

    country_aliases = {
        "Mexico": "México", "México": "México",
        "USA": "Estados Unidos", "United States": "Estados Unidos", "EE.UU.": "Estados Unidos",
        "France": "Francia", "España": "España", "Germany": "Alemania"
    }
    @staticmethod
    def extract_location_with_nlp(text):
            doc = BaseScraper.nlp(text)
            city = None
            state = None
            country = None

            locations = {"city": None, "state": None, "country": None}
            for ent in doc.ents:
                #print(ent.text, ent.label_)
                if ent.label_ in ("GPE", "LOC"):
                    ent_text = ent.text.strip()

                    # Normalizar país
                    if ent_text in BaseScraper.country_aliases:
                        locations["country"] = BaseScraper.country_aliases[ent_text]

                    # Normalizar estado
                    for country, states in BaseScraper.states_by_country.items():
                        if ent_text in states:
                            locations["state"] = ent_text
                            locations["country"] = country

                    # Abreviaturas
                    for country_code, abbrevs in BaseScraper.state_abbrevs.items():
                        if ent_text in abbrevs:
                            locations["state"] = abbrevs[ent_text]
                            for full_name, states in BaseScraper.states_by_country.items():
                                if abbrevs[ent_text] in states:
                                    locations["country"] = full_name

                    # Ciudad
                    if not locations["city"] and locations["state"] and ent_text != locations["state"]:
                        locations["city"] = ent_text

            return locations

class ElUniversalScraper(BaseScraper):
    """Scraper for El Universal."""

    HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "es-419,es;q=0.9,es-ES;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5,es-MX;q=0.4",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
    }
    
    async def get_article_links(self, search_query):
        search_query = search_query.replace(" ", "+")
        search_url = f"{self.base_url}/buscador/?query={search_query}"
        #print(search_url)
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
            next_pages = max(1, round(result_number / each_page_results))
            #next_pages = 2
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
        #with open("el_universal_soup.txt", "a", encoding="utf-8") as f:
        #    f.write("\n==================================================== Nuevo Soup ====================================================\n")
        #    f.write(soup.prettify())
        #    f.write("\n\n")

        script_tag = soup.find("script", id="fusion-metadata")
        data = ElUniversalScraper.get_page_keys(script_tag)

        #content = soup.find("script", text=re.compile(r'dataLayer\.push\(\{'))
        content = soup.find("script", string=re.compile(r'dataLayer\.push\(\{'))

        match = re.search(r'dataLayer\.push\((\{.*?\})\);', content.string, re.DOTALL)
        json_data = match.group(1)
        description_data = json.loads(json_data)
        titulo = description_data.get("titulo")
        descripcion = description_data.get("descripcion")
        
        descripcion_completa = " ".join(
            [tag.get_text(separator=" ", strip=True) for tag in soup.find_all("p", {"itemprop": "description", "class": "sc__font-paragraph"})]
        )

        full_description = f"{titulo}. {descripcion}. {descripcion_completa}".strip()

        locations = BaseScraper.extract_location_with_nlp(full_description)
        country = locations['country'] or "México"
        code = BaseScraper.codigo_pais(country)
        content_id = data.get('content_elements', [{}])[0].get('_id')

        #tokens = BaseScraper.word_count(full_description, palabras_objetivo)
        tokens = BaseScraper.word_count(full_description)
        #fecha = data.get('created_date') <--- Si fue modificado, aparece esta fecha.
        fecha = data.get('display_date') #<--- Fecha mostrada en la publicación del artículo
        fecha_normal = BaseScraper.normalizar_fecha(fecha)
        fecha_obj = datetime.strptime(fecha_normal, "%d/%m/%Y")
        if fecha_obj.year <2016:
            return
        else:
            article_info = {
                "ID_noticia": f"{code}{content_id}",
                "token": tokens,
                "fecha": fecha_normal,
                "diario": "El universal",
                "pais": country,
                "ubicación_noticia": locations['state']
            }
            return article_info
    
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
    
    async def get_article_links(self, search_query):
        search_query = search_query.replace(" ", "%20")
        timestamp = int(time.time() * 1000)
        search_url = f"{self.base_url}/search/{search_query}?time={timestamp}"
        #print(search_url)
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
            links = soup.select('div#middle.contenedor.contenedor-buscador div.fila a[href]')
            unique_links = set()
            for link in links: 
                href = link.get('href')
                if href and href.startswith('https://') and href not in unique_links:
                    unique_links.add(href)
                    all_links.append(href)

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
        #with open("la_jornada_soup.txt", "a", encoding="utf-8") as f:
        #    f.write("\n==================================================== Nuevo Soup ====================================================\n")
        #    f.write(soup.prettify())
        #    f.write("\n\n")

        script_tag = soup.find_all("script", type="application/ld+json")

        content = soup.find("div", id="middle", attrs={"class": "contenedor contenedor-detalle contenedor-article"})
        date = content.find("span", class_="nota-fecha")
        #print(script_tag)
        data = LaJornadaScraper.get_page_keys(script_tag)
        titulo = data.get('headline')
        descripcion = data.get('description')
        
        descripcion_completa = " ".join(
            [tag.get_text(separator=" ", strip=True) 
             for tag in (soup.find("div", id="content_nitf").find_all("p") 
                         if soup.find("div", id="content_nitf") else [])]
                         )
        full_description = f"{titulo}. {descripcion}. {descripcion_completa}".strip()
        
        locations = BaseScraper.extract_location_with_nlp(full_description)
        country = locations['country'] or "México"
        code = BaseScraper.codigo_pais(country)

        #print(locations)

        id = soup.find('div', {'data-widget-id': True})
        if id:
            identifier = id['data-widget-id']
        else: 
            identifier = None

        #tokens = BaseScraper.word_count(full_description, palabras_objetivo)
        tokens = BaseScraper.word_count(full_description)
        fecha = date.get_text(strip=True)
        fecha_normal = BaseScraper.normalizar_fecha(fecha)
        fecha_obj = datetime.strptime(fecha_normal, "%d/%m/%Y")
        if fecha_obj.year <2016:
            return
        else:
            article_info = {
                "ID_noticia": f"{code}{identifier}",
                "token": tokens,
                "fecha": fecha_normal,
                "diario": "La Jornada",
                "país": country,
                "ubicación_noticia": locations['state']
            }
            return article_info
    
    def get_page_keys(script_tag):
        for tag in script_tag:
            try:
                raw_text = tag.get_text()
                # Limpiar caracteres de control
                cleaned_text = re.sub(r'[\x00-\x1F\x7F]', '', raw_text)
                description_data = json.loads(cleaned_text)

                if isinstance(description_data, list):
                    for item in description_data:
                        if item.get("@type") == "NewsArticle":
                            return item
                elif description_data.get("@type") == "NewsArticle":
                    return description_data
            except json.JSONDecodeError as e:
                print("Error decoding JSON-LD:", e)
        return None



class MilenioScraper(BaseScraper):
    """Scraper for Reforma."""
    
    HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "es-419,es;q=0.9,es-ES;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5,es-MX;q=0.4",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
    }
    
    async def get_article_links(self, search_query):
        search_query = search_query.replace(" ", "+")
        search_url = f"{self.base_url}/buscador?text={search_query}"
        #print(search_url)
        browser = None
        all_links = []
        try:
            browser = await launch(
                executablePath=os.environ["PYPPETEER_BROWSER_EXECUTABLE"],
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.newPage()
            await page.setExtraHTTPHeaders(self.HEADERS)
            await page.goto(search_url, timeout=90000)
            await page.waitForSelector('input[name="text"]', {'timeout': 10000})

            #Simular la búsqueda para que muestre los resultados en el sou´p
            await page.evaluate(f'document.querySelector(\'input[name="text"]\').value = "{search_query}"')
            await page.click('button[type="submit"].secondary.rounded-soft')
            await asyncio.sleep(2)

            result = await page.content()
            soup = BeautifulSoup(result, 'html.parser')
            with open('resultado_milenio.html', 'w', encoding='utf-8') as file:
                file.write(soup.prettify())

            pages = soup.select_one('.search-controls__results__count')
            if not pages:
                #print(f"Available classes in soup: {[tag['class'] for tag in soup.find_all(class_=True)]}")
                print("Could not find count result div")
                return []
                
            result_text = pages.text.strip()
            print("Result text pages: ", result_text)
            match = re.search(r'Milenio:\s*(\d+)', result_text)
            if not match:
                print("No se encontró el número de resultados en la búsqueda.")
                return []
                
            result_number = int(match.group(1))
            each_page_results = 10
            next_pages = max(1, round(result_number / each_page_results))
            #next_pages = 2
            print(f"Found {result_number} results across {next_pages} pages")
            print("Reading page 1")
            links = soup.select('a.board-module__a')
            all_links.extend([self.base_url + link['href'] for link in links])

            if next_pages > 1:
                for _ in range(next_pages - 1): 
                    print(f"Reading page {_+2}") 
                    try:
                        next_button = await page.evaluate('''
                            () => {
                                const buttons = Array.from(document.querySelectorAll('a.board-module__a'));
                                const nextButton = buttons.find(el => {
                                    const span = el.querySelector('span.label');
                                    return span && span.textContent.trim() === 'SIGUIENTE';
                                });
                                return !!nextButton;  // Convertir a booleano
                            }
                        ''')
                        if not next_button:
                            print("No next button found")
                            break

                        is_visible = await page.evaluate('''
                            () => {
                                const buttons = Array.from(document.querySelectorAll('a.board-module__a'));
                                const nextButton = buttons.find(el => {
                                    const span = el.querySelector('span.label');
                                    return span && span.textContent.trim() === 'SIGUIENTE';
                                });
                                if (nextButton) {
                                    nextButton.click();
                                    return true;
                                }
                                return false;
                            }
                        ''')
                        if not is_visible:
                            print("Next button is not visible")
                            break
                        
                        #await next_button.click()
                        await page.waitForNavigation({'timeout': 30000})
                        #await asyncio.sleep(3)

                        content = await page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        links = soup.select('a.board-module__a')
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
        #print("Links de Milenio: ", all_links)
        return all_links
    
    def extract_article_data(self, article_url):
        response = requests.get(article_url)
        soup = BeautifulSoup(response.text, "html.parser")
        #with open("milenio_soup.txt", "a", encoding="utf-8") as f:
        #    f.write("\n==================================================== Nuevo Soup ====================================================\n")
        #    f.write(soup.prettify())
        #    f.write("\n\n")
        script_tags = soup.find_all("script", type="application/ld+json")
        data = MilenioScraper.get_page_keys(script_tags)
        titulo = data[0].get('headline')
        subtitulo = data[0].get('alternativeHeadline')
        descripcion = data[0].get('description')
        cuerpo = data[0].get('articleBody')


        content = soup.find("div", class_="content-columns nws")
        content_date_div = soup.find("div", class_="content-date")
        section = soup.find("section", class_="content-art-info")
        logora_div = soup.find("div", class_="logora_synthese")
        full_description = f"{titulo}. {descripcion}. {subtitulo}. {cuerpo}".strip()

        locations = BaseScraper.extract_location_with_nlp(full_description)
       
        location = None
        author = None
        identifier = None
        keywords = []
        

        if content_date_div:
            location_span = content_date_div.find("span", class_="location", itemprop="contentLocation")
            if location_span:
                location = location_span.get_text(strip=True)
        
        country = locations['country'] or "México"
        code = BaseScraper.codigo_pais(country)

        if section:
            author_tag = section.find("span", class_="author")
            if author_tag:
                author = author_tag.get_text(strip=True)
        

        if logora_div:
            identifier = logora_div.get("data-identifier")
        

        keyword_links = soup.find_all("a", class_="nd-tags-detail-base__tag", itemprop="keywords")
        for kw in keyword_links:
            keyword = kw.get_text(strip=True)
            if keyword:
                keywords.append(keyword)

        #tokens = BaseScraper.word_count(full_description, palabras_objetivo)
        tokens = BaseScraper.word_count(full_description)
        fecha = data[0].get('datePublished')
        fecha_normal = BaseScraper.normalizar_fecha(fecha)
        fecha_obj = datetime.strptime(fecha_normal, "%d/%m/%Y")
        if fecha_obj.year <2016:
            return
        else:
            article_info = {
                "ID_noticia": f"{code}{identifier}", # <div class="logora_synthese" data-identifier="1935755" data-object-id="logora_config">
                "token": tokens,
                "fecha": fecha_normal,
                "diario": "Milenio",
                "país": country,
                "ubicación_noticia": locations['state']
            }
            return article_info
    
    def get_page_keys(script_tag):
        if not script_tag:
            print("No script_tag**************************")
            return {}
        extracted_data = []

        for tag in script_tag:
            try:
                data = json.loads(tag.string.strip())
                extracted_data.append(data)
            except json.JSONDecodeError as e:
                print("Error decoding JSON-LD:", e)

        return extracted_data

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
            'milenio': MilenioScraper('https://www.milenio.com')
        }
        self.output_file = output_file
    
    async def scrape(self, site, query):
        scraper = self.scrapers.get(site)
        if not scraper:
            raise ValueError(f"No scraper found for {site}")
        
        links = await scraper.get_article_links(query)
        new_articles = []
        
        for link in links: 
            print(link)
            try:
                #articles.append(scraper.extract_article_data(link))
                new_articles.append(scraper.extract_article_data(link))
                #new_articles = [scraper.extract_article_data(links[0])] if links else []

            except Exception as e:
                print(f"Error processing article {link}: {e}")
        
        #with open(self.output_file, "w", encoding="utf-8") as file:
        #    json.dump(articles, file, indent=4, ensure_ascii=False)
        
        existing_articles = []
        if os.path.exists(self.output_file) and os.path.getsize(self.output_file) > 0:
            try:
                with open(self.output_file, "r", encoding="utf-8") as file:
                    existing_articles = json.load(file)
            except json.JSONDecodeError:
                print(f"Error reading existing JSON file. Creating new file.")

        
        all_articles = existing_articles + new_articles
        with open(self.output_file, "w", encoding="utf-8") as file:
            json.dump(all_articles, file, indent=4, ensure_ascii=False)

        return all_articles

if __name__ == "__main__":
    ws = WebScraper()

    palabras_objetivo = BaseScraper.cargar_terminos()
    
    # Lista de periódicos a buscar
    newspapers = [
        'el_universal',
        'milenio',
        'la_jornada'
    ]
    
    # Lista de términos de búsqueda
    search_terms = [
        #'feminicidio'
        'violencia+de+género',
        #'violencia+vicaria',
        #'machismo',
        #'violencia+intrafamiliar'
    ]
    
    all_results = {}
    
    # Realizar búsqueda para cada periódico y término
    for newspaper in newspapers:
        print(f"\n=== Buscando en {newspaper.replace('_', ' ').title()} ===")
        all_results[newspaper] = {}
        
        #for term in search_terms:
        for term in palabras_objetivo:
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