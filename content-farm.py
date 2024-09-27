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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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

client = Groq(api_key=GROQ_API_KEY)

# Configurable parameters
CONTENT_DIR = os.path.join(os.path.dirname(__file__), 'site', 'content', 'articles')
INDEX_FILE = os.path.join(CONTENT_DIR, 'articles_index.json')
ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), 'site_analytics.json')
MAX_TOPIC_LENGTH = 100
SIMILARITY_THRESHOLD = 0.7
TOP_N_TERMS = 50  # Number of top terms to consider as covered
SLEEP_TIME_BETWEEN_TOPICS = 2  # seconds
SLEEP_TIME_BETWEEN_ITERATIONS = 600  # seconds

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

def topic_generator_agent(existing_topics, underrepresented_topics):
    """
    Generates a list of unique, in-depth article topics.
    """
    logging.info("Generating new topics...")
    # Limit the number of topics included in the prompt to avoid exceeding prompt size limits
    existing_topics_sample = existing_topics[:20]
    underrepresented_topics_sample = underrepresented_topics[:20]

    prompt = (
        "Generate a list of 10 unique, in-depth article topics that explore detailed and technical aspects of the Solana blockchain.\n"
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

def writer_agent(topic):
    """
    Writes a detailed and technical article on the given topic.
    """
    logging.info("Writing article for topic: '%s'", topic)
    prompt = (
        f"Write a detailed and technical article about the following topic:\n{topic}\n"
        "The article should be comprehensive, well-structured, and informative."
    )
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.2-90b-text-preview",
        )
        article = response.choices[0].message.content
        return article
    except Exception as e:
        logging.error("Error writing article for topic '%s': %s", topic, e)
        return None

def seo_agent(article):
    """
    Optimizes the article for SEO.
    """
    logging.info("Optimizing article for SEO.")
    prompt = (
        f"Optimize the following article for SEO. Include relevant keywords, meta descriptions, and ensure it adheres to best SEO practices:\n\n{article}"
    )
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.2-90b-text-preview",
        )
        optimized_article = response.choices[0].message.content
        return optimized_article
    except Exception as e:
        logging.error("Error optimizing article for SEO: %s", e)
        return None

def front_end_agent(article_content, title):
    """
    Saves the article content to a Markdown file with appropriate front matter.
    """
    logging.info("Saving article '%s' to Markdown file.", title)
    filename = title.lower().replace(' ', '-').replace('/', '-').replace(':', '').replace('"', '')[:50] + '.md'
    filepath = os.path.join(CONTENT_DIR, filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    front_matter = f"""---
title: "{title}"
date: "{time.strftime('%Y-%m-%d')}"
---

"""
    full_content = front_matter + article_content

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(full_content)
        logging.info("Article '%s' has been saved to %s", title, filepath)
        return filepath
    except Exception as e:
        logging.error("Error saving article '%s' to file: %s", title, e)
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
            if max_similarity > SIMILARITY_THRESHOLD:
                logging.warning(
                    "Content similar to existing articles detected (similarity: %.2f). Skipping article '%s'.",
                    max_similarity, title
                )
                return False
        except Exception as e:
            logging.error("Error during content similarity check: %s", e)
            # Decide whether to skip the article or not; here we proceed cautiously
            return False

    return True

def deployment_agent(filepaths):
    """
    Deploys new articles by committing and pushing to the Git repository.
    """
    logging.info("Deploying new articles...")
    try:
        # Ensure we have the latest changes from the remote repository
        origin = repo.remote(name='origin')
        logging.info("Fetching changes from the remote repository...")
        origin.fetch()
        logging.info("Successfully fetched changes.")

        logging.info("Merging remote changes into local repository...")
        repo.git.merge(f'origin/{repo.active_branch.name}')
        logging.info("Successfully merged remote changes.")

        # Add new files to Git
        repo.git.add(A=True)

        if repo.is_dirty(untracked_files=True):
            commit_message = f"Add new articles: {', '.join(os.path.basename(fp) for fp in filepaths)}"
            repo.index.commit(commit_message)
            logging.info("Committed changes with message: '%s'", commit_message)

            # Push to remote repository
            logging.info("Pushing changes to the remote repository...")
            origin.push()
            logging.info("Successfully pushed changes.")
        else:
            logging.info("No changes to commit.")
    except git.exc.GitCommandError as e:
        logging.error("Git command error: %s", e)
        if 'non-fast-forward' in str(e):
            logging.warning("Non-fast-forward error detected. The local repository is behind the remote repository.")
            logging.info("Attempting to pull and merge remote changes...")
            try:
                repo.git.pull('--rebase')
                logging.info("Successfully pulled and merged remote changes.")
                logging.info("Retrying to push changes...")
                repo.git.push()
                logging.info("Successfully pushed changes after pulling.")
            except Exception as pull_error:
                logging.error("Failed to pull and push changes: %s", pull_error)
                logging.error("Manual intervention required to resolve merge conflicts.")
        else:
            logging.error("An unexpected Git error occurred: %s", e)
    except Exception as e:
        logging.error("Unexpected error during deployment: %s", e)

def load_existing_articles():
    """
    Loads existing articles metadata from the index file.
    """
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    existing_articles = json.loads(content)
                else:
                    logging.warning("Index file '%s' is empty. Initializing with an empty dictionary.", INDEX_FILE)
                    existing_articles = {}
        except json.JSONDecodeError as e:
            logging.error("Error decoding JSON from '%s': %s", INDEX_FILE, e)
            logging.info("Initializing with an empty dictionary.")
            existing_articles = {}
        except Exception as e:
            logging.error("Error reading index file '%s': %s", INDEX_FILE, e)
            existing_articles = {}
    else:
        logging.info("Index file '%s' does not exist. Initializing with an empty dictionary.", INDEX_FILE)
        existing_articles = {}
    return existing_articles

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

def main():
    """
    Main function that orchestrates the agents to generate and deploy articles.
    """
    logging.info("Starting the content generation loop.")
    while not shutdown_flag:
        try:
            existing_articles = load_existing_articles()
            if not isinstance(existing_articles, dict):
                logging.error("Existing articles data is not a dictionary. Resetting to empty dictionary.")
                existing_articles = {}
            existing_titles = list(existing_articles.keys())

            underrepresented_topics = analyze_existing_topics(existing_articles)

            logging.info(
                "Generating new topics based on %d existing articles and %d underrepresented topics.",
                len(existing_titles), len(underrepresented_topics)
            )
            topics = topic_generator_agent(existing_titles, underrepresented_topics)

            if not topics:
                logging.warning("No new topics generated. Sleeping before retrying.")
                time.sleep(SLEEP_TIME_BETWEEN_ITERATIONS)
                continue

            filepaths = []
            for topic in topics:
                if shutdown_flag:
                    logging.info("Shutdown flag detected. Exiting topic processing loop.")
                    break
                try:
                    if len(topic) > MAX_TOPIC_LENGTH:
                        logging.warning("Skipping overly long topic: %s...", topic[:MAX_TOPIC_LENGTH])
                        continue
                    logging.info("Processing topic: '%s'", topic)

                    article = writer_agent(topic)
                    if not article:
                        continue

                    optimized_article = seo_agent(article)
                    if not optimized_article:
                        continue

                    if content_moderation_agent(topic, optimized_article, existing_articles):
                        filepath = front_end_agent(optimized_article, title=topic)
                        if filepath:
                            filepaths.append(filepath)
                            update_existing_articles(existing_articles, topic, optimized_article)
                            logging.info("Article '%s' added to index and saved to '%s'", topic, filepath)
                    else:
                        logging.info("Article '%s' was skipped due to duplication.", topic)
                except Exception as e:
                    logging.error("Error processing topic '%s': %s", topic, e)
                    continue  # Proceed to the next topic

                time.sleep(SLEEP_TIME_BETWEEN_TOPICS)

            if filepaths:
                deployment_agent(filepaths)
            else:
                logging.info("No new articles to deploy.")

            logging.info("Sleeping for %d seconds before generating new topics...", SLEEP_TIME_BETWEEN_ITERATIONS)
            time.sleep(SLEEP_TIME_BETWEEN_ITERATIONS)
        except Exception as e:
            logging.error("Error in main loop: %s", e, exc_info=True)
            logging.info("Sleeping for 60 seconds before retrying.")
            time.sleep(60)

    logging.info("Content generation loop has been terminated.")

if __name__ == "__main__":
    main()




