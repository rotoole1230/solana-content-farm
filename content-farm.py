import os
import time
import git
import json
import signal
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import openai
import requests
from datetime import datetime
from slugify import slugify
import httpx
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed from logging.INFO to logging.DEBUG
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        # You can add a FileHandler here to log to a file if desired
    ]
)

# Load environment variables from .env file
load_dotenv()

# Initialize the Groq client with your API key
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    logging.error("GROQ_API_KEY is not set in environment variables.")
    sys.exit(1)
else:
    logging.debug("GROQ_API_KEY is set.")

client = Groq(api_key=GROQ_API_KEY)

# Load OpenAI API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY is not set in environment variables.")
    sys.exit(1)
else:
    logging.debug("OPENAI_API_KEY is set.")

openai.api_key = OPENAI_API_KEY

# Configurable parameters
CONTENT_DIR = os.path.join(os.path.dirname(__file__), 'site', 'content', 'articles')
INDEX_FILE = os.path.join(CONTENT_DIR, 'articles_index.json')
ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), 'site_analytics.json')
MAX_TOPIC_LENGTH = 120
SIMILARITY_THRESHOLD = 0.7
TOP_N_TERMS = 50  # Number of top terms to consider as covered
SLEEP_TIME_BETWEEN_TOPICS = 10   # Increase delay between topics to 10 seconds
SLEEP_TIME_BETWEEN_ITERATIONS = 900  # Increase delay between iterations to 15 minutes
GENERATE_VISUALIZATIONS = False  # Set to True to enable visualizations

# Ensure content directory exists
if not os.path.exists(CONTENT_DIR):
    os.makedirs(CONTENT_DIR)
    logging.info("Created content directory at %s", CONTENT_DIR)
else:
    logging.debug("Content directory exists: %s", CONTENT_DIR)

# Initialize Git repository
try:
    repo_path = os.path.dirname(os.path.abspath(__file__))
    repo = git.Repo(repo_path)
except git.exc.InvalidGitRepositoryError:
    logging.error("Error: Not a valid Git repository at path '%s'.", repo_path)
    sys.exit(1)
except Exception as e:
    logging.error("An unexpected error occurred while initializing the Git repository: %s", e)
    sys.exit(1)

# Flag to control graceful shutdown
shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    logging.info("Shutdown signal received. Exiting gracefully...")
    shutdown_flag = True

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Rate limiting variables
api_lock = threading.Lock()
MIN_API_CALL_INTERVAL = 1.0  # Minimum interval in seconds between API calls

def rate_limited(func):
    def wrapper(*args, **kwargs):
        with api_lock:
            now = time.time()
            since_last_call = now - wrapper.last_call
            if since_last_call < MIN_API_CALL_INTERVAL:
                sleep_time = MIN_API_CALL_INTERVAL - since_last_call
                logging.debug("Rate limiting API call. Sleeping for %.2f seconds.", sleep_time)
                time.sleep(sleep_time)
            result = func(*args, **kwargs)
            wrapper.last_call = time.time()
            return result
    wrapper.last_call = 0.0
    return wrapper

@rate_limited
def topic_generation_agent(existing_topics, underrepresented_topics):
    """
    Generates a list of unique, in-depth article topics.
    """
    logging.info("Generating new topics...")
    # Limit the number of topics included in the prompt to avoid exceeding prompt size limits
    existing_topics_sample = existing_topics[:20]
    underrepresented_topics_sample = underrepresented_topics[:20]

    prompt = (
        "Generate a list of 10 unique, in-depth article topics that explore detailed and technical aspects of the Solana blockchain.\n"
        "Each topic should be concise and no longer than 100 characters.\n"
        f"Avoid topics that have already been covered: {existing_topics_sample}.\n"
        f"Focus on these underrepresented areas: {underrepresented_topics_sample}.\n"
        "Suggest areas that can be expounded upon differently.\n"
        "Return each topic on a new line, without numbering."
    )
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.2-90b-text-preview",
        )
        topics = response.choices[0].message.content
        topics_list = [topic.strip() for topic in topics.split('\n') if topic.strip()]
        return topics_list
    except Exception as e:
        logging.error("Error generating topics: %s", e)
        return []

@rate_limited
def writer_agent(topic):
    """
    Writes a detailed and technical article on the given topic.
    """
    logging.info("Writing article for topic: '%s'", topic)
    prompt = (
        f"Write a detailed and technical article about '{topic}' suitable for blockchain developers and enthusiasts."
    )
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.2-90b-text-preview",
        )
        logging.debug("Writer agent response: %s", response)
        article = response.choices[0].message.content.strip()
        if not article:
            logging.warning("Empty article received from writer agent for topic '%s'.", topic)
            return None
        else:
            logging.debug("Writer agent produced article: %s", article)
            return article
    except Exception as e:
        logging.error("Error generating article for topic '%s': %s", topic, e, exc_info=True)
        return None

@rate_limited
def seo_agent(article):
    """
    Optimizes the article for SEO by adding metadata, keywords, header tags, and internal links.
    """
    logging.info("Optimizing article for SEO.")
    prompt = (
        "Optimize the following article for SEO by adding metadata, keywords, header tags, and internal links where appropriate.\n\n"
        "Article:\n" + article
    )
    max_retries = 3
    retry_delay = 5  # Start with a 5-second delay
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.2-90b-text-preview",
            )
            logging.debug("SEO agent response: %s", response)
            optimized_article = response.choices[0].message.content.strip()
            if not optimized_article:
                logging.warning("Empty optimized article received from SEO agent.")
                return None
            else:
                logging.debug("SEO agent optimized article: %s", optimized_article)
                return optimized_article
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', '60'))
                logging.error("Rate limit error in SEO agent: %s", e)
                if attempt < max_retries - 1:
                    logging.info("Retrying SEO optimization in %d seconds...", retry_after)
                    time.sleep(retry_after)
                    continue
                else:
                    logging.error("Max retries reached in SEO agent. Skipping optimization.")
                    return None
            else:
                logging.error("HTTP error in SEO agent: %s", e)
                return None
        except Exception as e:
            logging.error("Error optimizing article: %s", e, exc_info=True)
            return None

def front_end_agent(optimized_article, title):
    """
    Formats the article for the front-end, optionally generates visualizations, and saves it to the content directory.
    """
    logging.info("Formatting article for front-end.")
    filename = f"{slugify(title)}.md"
    filepath = os.path.join(CONTENT_DIR, filename)
    
    image_paths = []
    
    if GENERATE_VISUALIZATIONS:
        logging.info("Determining if visualizations are needed for the article.")
        image_paths = visualization_agent(optimized_article)
    else:
        logging.info("Visualization generation is disabled.")
    
    # Proceed with saving the article as usual
    try:
        with open(filepath, 'w') as f:
            f.write(optimized_article)
        logging.info("Article saved to %s", filepath)
        return filepath
    except Exception as e:
        logging.error("Error saving article to %s: %s", filepath, e, exc_info=True)
        return None

def content_moderation_agent(title, article_content, existing_articles):
    """
    Checks for duplication in titles and content.
    """
    logging.info("Moderating content for article '%s'.", title)
    existing_titles_lower = [t.lower() for t in existing_articles.keys()]
    if title.lower() in existing_titles_lower:
        logging.warning("Duplicate title detected: '%s'. Skipping article.", title)
        return False

    if existing_articles:
        articles = list(existing_articles.values())
        try:
            vectorizer = TfidfVectorizer().fit_transform([article_content] + articles)
            vectors = vectorizer.toarray()
            cosine_matrix = cosine_similarity(vectors[0:1], vectors[1:])
            max_similarity = cosine_matrix.max()
            logging.debug("Content similarity for '%s': %.2f", title, max_similarity)
            if max_similarity > SIMILARITY_THRESHOLD:
                logging.warning(
                    "Content similar to existing articles detected (similarity: %.2f). Skipping article '%s'.",
                    max_similarity, title
                )
                return False
        except Exception as e:
            logging.error("Error during content similarity check: %s", e, exc_info=True)
            # Proceed cautiously if an error occurs
            return True
    else:
        logging.info("No existing articles found. Proceeding with the new article.")

    return True

def deployment_agent(filepaths):
    """
    Handles deployment of the new articles.
    """
    logging.info("Deploying articles...")
    try:
        # Stage new files
        repo.index.add(filepaths)
        logging.debug("Staged files for commit: %s", filepaths)

        # Commit changes
        commit_message = "Automated content update"
        commit = repo.index.commit(commit_message)
        logging.info("Committed changes with message: '%s'", commit_message)
        logging.debug("Commit details: %s", commit)

        # Push changes
        origin = repo.remote(name='origin')
        push_info = origin.push()
        for info in push_info:
            if info.flags & info.ERROR:
                logging.error("Push error: %s", info.summary)
            else:
                logging.info("Push success: %s", info.summary)
        logging.info("Pushed changes to remote repository.")
    except Exception as e:
        logging.error("Error during deployment: %s", e, exc_info=True)

def load_existing_articles():
    """
    Loads existing articles from the index file.
    """
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r') as f:
            return json.load(f)
    return {}

def update_existing_articles(existing_articles, title, article_content):
    """
    Updates the index file with new article metadata.
    """
    existing_articles[title] = article_content
    try:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_articles, f, ensure_ascii=False, indent=2)
        logging.info("Updated index file '%s' with new article: '%s'", INDEX_FILE, title)
    except Exception as e:
        logging.error("Error updating index file '%s': %s", INDEX_FILE, e)

def analyze_existing_topics(existing_articles):
    """
    Analyzes existing articles to find underrepresented topics.
    """
    logging.info("Analyzing existing articles to find underrepresented topics.")
    if not existing_articles:
        return []
    try:
        articles_content = list(existing_articles.values())
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        tfidf_matrix = vectorizer.fit_transform(articles_content)
        feature_array = vectorizer.get_feature_names_out()
        tfidf_sorting = tfidf_matrix.toarray().sum(axis=0)
        top_terms = feature_array[tfidf_sorting.argsort()[-TOP_N_TERMS:]]
        underrepresented_terms = list(set(feature_array) - set(top_terms))
        return underrepresented_terms
    except Exception as e:
        logging.error("Error analyzing existing topics: %s", e)
        return []

def visualization_agent(article_content):
    """
    Visualization generation is temporarily disabled.
    """
    logging.info("Visualization generation is currently disabled.")
    return []

def main():
    """
    Main function that orchestrates the agents to generate and deploy articles.
    """
    logging.info("Starting the content generation loop.")
    existing_articles = load_existing_articles()
    existing_topics = list(existing_articles.keys())
    logging.debug("Loaded existing topics: %s", existing_topics)

    underrepresented_topics = ["Solana's BPF VM", "Solana's Transaction Processing", "Solana's Tokenomics"]
    logging.debug("Underrepresented topics: %s", underrepresented_topics)

    while not shutdown_flag:
        try:
            topics = topic_generation_agent(existing_topics, underrepresented_topics)
            logging.debug("Generated topics: %s", topics)
            if not topics:
                logging.warning("No topics generated. Sleeping before next iteration.")
                time.sleep(SLEEP_TIME_BETWEEN_ITERATIONS)
                continue

            filepaths = []
            for topic in topics:
                if shutdown_flag:
                    logging.info("Shutdown flag detected. Exiting topic processing loop.")
                    break

                if len(topic) > MAX_TOPIC_LENGTH:
                    logging.warning("Skipping topic exceeding length limit (%d characters): %s", len(topic), topic)
                    continue  # Skip this topic and proceed to the next one

                try:
                    logging.info("Processing topic: '%s'", topic)

                    article = writer_agent(topic)
                    if not article:
                        logging.warning("No article generated for topic '%s'. Skipping.", topic)
                        continue

                    optimized_article = seo_agent(article)
                    if not optimized_article:
                        logging.warning("SEO optimization failed for article on topic '%s'. Skipping.", topic)
                        continue

                    if content_moderation_agent(topic, optimized_article, existing_articles):
                        filepath = front_end_agent(optimized_article, title=topic)
                        if filepath:
                            filepaths.append(filepath)
                            update_existing_articles(existing_articles, topic, optimized_article)
                            existing_topics.append(topic)  # Update existing topics
                            logging.info("Article '%s' added to index and saved to '%s'", topic, filepath)
                        else:
                            logging.warning("Failed to save article '%s'.", topic)
                    else:
                        logging.info("Article '%s' was skipped due to duplication or similarity.", topic)
                except Exception as e:
                    logging.error("Error processing topic '%s': %s", topic, e, exc_info=True)
                    continue  # Proceed to the next topic

                time.sleep(SLEEP_TIME_BETWEEN_TOPICS)

            if filepaths:
                deployment_agent(filepaths)
            else:
                logging.info("No new articles to deploy.")

            # Sleep at the end of the main loop
            logging.info("Sleeping for %d seconds before generating new topics...", SLEEP_TIME_BETWEEN_ITERATIONS)
            time.sleep(SLEEP_TIME_BETWEEN_ITERATIONS)
        except Exception as e:
            logging.error("Error in main loop: %s", e, exc_info=True)
            logging.info("Sleeping for 60 seconds before retrying.")
            time.sleep(60)

    logging.info("Content generation loop has been terminated.")

if __name__ == "__main__":
    main()