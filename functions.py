import os
import subprocess
import requests
from bs4 import BeautifulSoup


def run_shell_command(command_json):
    command = command_json.get("command")
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return {"output": result.stdout, "error": result.stderr}
    except subprocess.CalledProcessError as e:
        return {"output": e.stdout, "error": e.stderr}

def list_directory_contents(path_json):
    path = path_json.get("path", ".")
    try:
        files = os.listdir(path)
        return {"files": files}
    except Exception as e:
        return {"error": str(e)}

def edit_file(file_json):
    file_path = file_json.get("file_path")
    content = file_json.get("content")
    try:
        with open(file_path, 'w') as file:
            file.write(content)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}



def perform_google_search(query_json, page=1):
    # importwet_trace()
    # Set up API keys and engine ID
    API_KEY = os.getenv("GOOGLE_API_KEY")
    SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    query = query_json.get("query")

    # Constructing the URL
    start = (page - 1) * 10 + 1
    url = f"https://www.googleapis.com/customsearch/v1?key={API_KEY}&cx={SEARCH_ENGINE_ID}&q={query}&start={start}"

    # Make the API request
    data = requests.get(url).json()

    # Collect and prepare the results
    results = []
    search_items = data.get("items")
    if search_items:
        for i, search_item in enumerate(search_items, start=1):
            try:
                long_description = search_item["pagemap"]["metatags"][0]["og:description"]
            except KeyError:
                long_description = "N/A"

            # Collect necessary details
            result = {
                "title": search_item.get("title"),
                "snippet": search_item.get("snippet"),
                "long_description": long_description,
                "link": search_item.get("link")
            }
            results.append(result)

    return results

def web_scrape(urls_json):
    results = {}
    urls = urls_json.get("urls")
    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extract text content, here using all paragraphs
        text_content = ' '.join([p.text for p in soup.find_all('p')])
        results[url] = text_content  # Store text with URL as key
    return results