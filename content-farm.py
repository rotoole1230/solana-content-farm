import os
import json
# ... other imports ...

# Update the INDEX_FILE path
CONTENT_DIR = os.path.join(os.path.dirname(__file__), 'site', 'content', 'articles')
INDEX_FILE = os.path.join(CONTENT_DIR, 'articles_index.json')

def update_existing_articles(existing_articles, title, article_content):
    existing_articles[title] = article_content
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_articles, f, ensure_ascii=False, indent=2)
    print(f"Updated {INDEX_FILE} with new article: {title}")

def load_existing_articles():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def cleanup_extra_index_files():
    for root, dirs, files in os.walk(os.path.dirname(CONTENT_DIR)):
        for file in files:
            if file == 'articles_index.json' and os.path.join(root, file) != INDEX_FILE:
                os.remove(os.path.join(root, file))
                print(f"Removed extra index file: {os.path.join(root, file)}")

def main():
    cleanup_extra_index_files()
    while True:
        try:
            existing_articles = load_existing_articles()
            # ... rest of the main function ...
        except Exception as e:
            print(f"An error occurred: {e}")
            break
        finally:
            print("Iteration complete")