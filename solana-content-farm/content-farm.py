import os
import time
import git
from groq import Groq
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

# Initialize the Groq client with your API key
load_dotenv()  # This loads the variables from .env

client = Groq(
    api_key=os.getenv('GROQ_API_KEY'),
)

# Paths to directories and files
CONTENT_DIR = os.path.join(os.path.dirname(__file__), 'site', 'content', 'articles')
INDEX_FILE = os.path.join(CONTENT_DIR, 'articles_index.json')
ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), 'site_analytics.json')

# Initialize Git repository
repo = git.Repo(os.path.dirname(os.path.abspath(__file__)))

# Agent 1: Topic Generator Agent
def topic_generator_agent(existing_topics, underrepresented_topics):
    prompt = (
        "Generate a list of 10 unique, in-depth article topics that explore detailed and technical aspects of the Solana blockchain. "
        f"Avoid topics that have already been covered: {existing_topics}. "
        f"Focus on these underrepresented areas: {underrepresented_topics}. "
        "Suggest areas that can be expounded upon differently. "
        "Return each topic on a new line, without numbering."
    )
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-90b-text-preview",
    )
    topics = response.choices[0].message.content
    # Process topics into a list
    topics_list = [topic.strip() for topic in topics.split('\n') if topic.strip()]
    return topics_list

# Agent 2: Writer Agent
def writer_agent(topic):
    prompt = (
        f"Write a detailed and technical article about the following topic:\n{topic}\n"
        "The article should be comprehensive, well-structured, and informative."
    )
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-90b-text-preview",
    )
    article = response.choices[0].message.content
    return article

# Agent 3: SEO Agent
def seo_agent(article):
    prompt = (
        f"Optimize the following article for SEO. Include relevant keywords, meta descriptions, and ensure it adheres to best SEO practices:\n\n{article}"
    )
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-90b-text-preview",
    )
    optimized_article = response.choices[0].message.content
    return optimized_article

# Agent 4: Front-End Agent
def front_end_agent(article_content, title):
    # Generate a filename based on the title
    filename = title.lower().replace(' ', '-').replace('/', '-').replace(':', '').replace('"', '')[:50] + '.md'
    filepath = os.path.join(CONTENT_DIR, filename)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Create front matter for the Markdown file
    front_matter = f"""---
title: "{title}"
date: "{time.strftime('%Y-%m-%d')}"
---

"""
    # Combine front matter and article content
    full_content = front_matter + article_content
    
    # Write the content to a Markdown file
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(full_content)
    
    print(f"Article '{title}' has been saved to {filepath}")
    return filepath

# Agent 5: Content Moderation Agent
def content_moderation_agent(title, article_content, existing_articles):
    # Check for duplication in titles
    existing_titles_lower = [t.lower() for t in existing_articles.keys()]
    if title.lower() in existing_titles_lower:
        print(f"Duplicate title detected: '{title}'. Skipping article.")
        return False
    
    # Check for substantial duplication in content using TF-IDF similarity
    if existing_articles:
        articles = list(existing_articles.values())
        vectorizer = TfidfVectorizer().fit_transform([article_content] + articles)
        vectors = vectorizer.toarray()
        
        # Compute cosine similarity between new article and existing articles
        cosine_matrix = cosine_similarity(vectors[0:1], vectors[1:])
        max_similarity = cosine_matrix.max()
        
        # If similarity is above threshold, consider it duplicate
        if max_similarity > 0.7:
            print(f"Content similar to existing articles detected (similarity: {max_similarity:.2f}). Skipping article '{title}'.")
            return False
    
    # Article passes moderation
    return True

# Agent 6: Deployment Agent
def deployment_agent(filepaths):
    try:
<<<<<<< HEAD:content-farm.py
        origin = repo.remote(name='origin')

        # Fetch changes from the remote repository
        print("Fetching changes from the remote repository...")
        origin.fetch()
        print("Successfully fetched changes.")

        # Merge remote changes into local repository
        print("Merging remote changes into local repository...")
        repo.git.merge(f'origin/{repo.active_branch.name}')
        print("Successfully merged remote changes.")

=======
>>>>>>> 1c8123e9e0ca7984ce41638ec9b09f5deebeb4c0:solana-content-farm/content-farm.py
        # Add new files to Git
        repo.git.add(A=True)
        
        # Check if there are changes to commit
        if repo.is_dirty(untracked_files=True):
            # Commit changes
            commit_message = f"Add new articles: {', '.join(os.path.basename(fp) for fp in filepaths)}"
            repo.index.commit(commit_message)
<<<<<<< HEAD:content-farm.py
            print(f"Committed changes with message: '{commit_message}'")
            
            # Push to remote repository
            print("Pushing changes to the remote repository...")
            push_info = origin.push()
            
            # Check push results
=======
            
            # Push to remote repository
            origin = repo.remote(name='origin')
            push_info = origin.push()
            
>>>>>>> 1c8123e9e0ca7984ce41638ec9b09f5deebeb4c0:solana-content-farm/content-farm.py
            if push_info:
                for info in push_info:
                    if info.flags & info.ERROR:
                        print(f"Error pushing to repository: {info.summary}")
                    else:
<<<<<<< HEAD:content-farm.py
                        print(f"Successfully pushed to {info.remote_ref.name}")
            else:
                print("Push completed with no information.")
=======
                        print(f"Successfully pushed to {info.remote_ref_string}")
            else:
                print("No changes to push.")
>>>>>>> 1c8123e9e0ca7984ce41638ec9b09f5deebeb4c0:solana-content-farm/content-farm.py
        else:
            print("No changes to commit.")
    except git.exc.GitCommandError as e:
        print(f"Git command error: {e}")
<<<<<<< HEAD:content-farm.py
        if 'non-fast-forward' in e.stderr:
            print("Non-fast-forward error detected. The local repository is behind the remote repository.")
            print("Attempting to pull and merge remote changes...")
            try:
                repo.git.pull()
                print("Successfully pulled and merged remote changes.")
                print("Retrying to push changes...")
                repo.git.push()
                print("Successfully pushed changes after pulling.")
            except Exception as pull_error:
                print(f"Failed to pull and push changes: {pull_error}")
                print("Manual intervention required to resolve merge conflicts.")
        else:
            print("An unexpected Git error occurred.")
=======
>>>>>>> 1c8123e9e0ca7984ce41638ec9b09f5deebeb4c0:solana-content-farm/content-farm.py
    except Exception as e:
        print(f"Unexpected error during deployment: {e}")

# Agent 7: Marketing and Advertising Agent (Inactive Initially)
def marketing_agent(budget, analytics_data):
    # Placeholder function for future implementation
    """
    This agent will:
    - Analyze site analytics to identify high-performing content.
    - Determine the best channels (Meta Ads, Google Ads) for advertising.
    - Allocate the budget to campaigns with the highest ROI potential.
    - Monitor campaign performance and adjust strategies accordingly.
    - Generate reports on marketing ROI and insights for optimization.
    """
    # Example of what the agent might do (code not active)
    # Analyze analytics data
    # high_traffic_articles = analyze_analytics(analytics_data)
    # Plan advertising campaigns based on high-traffic articles
    # campaigns = plan_ad_campaigns(high_traffic_articles, budget)
    # Execute campaigns (interact with advertising APIs)
    # execute_campaigns(campaigns)
    pass  # Functionality to be implemented later

# Helper function to load existing articles metadata
def load_existing_articles():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    existing_articles = json.loads(content)
                else:
                    print(f"Warning: {INDEX_FILE} is empty. Initializing with an empty dictionary.")
                    existing_articles = {}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {INDEX_FILE}: {e}")
            print("Initializing with an empty dictionary.")
            existing_articles = {}
    else:
        print(f"{INDEX_FILE} does not exist. Initializing with an empty dictionary.")
        existing_articles = {}
    return existing_articles

# Helper function to update articles metadata
def update_existing_articles(existing_articles, title, article_content):
    existing_articles[title] = article_content
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_articles, f, ensure_ascii=False, indent=2)
    print(f"Updated {INDEX_FILE} with new article: {title}")

# Helper function to analyze existing articles and find underrepresented topics
def analyze_existing_topics(existing_articles):
    if not existing_articles:
        return []
    # Extract content from existing articles
    articles_content = list(existing_articles.values())
    # Use TF-IDF to find important terms
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    tfidf_matrix = vectorizer.fit_transform(articles_content)
    feature_array = vectorizer.get_feature_names_out()
    tfidf_sorting = tfidf_matrix.toarray().sum(axis=0)
    top_n = 50  # Number of top terms to consider as covered
    top_terms = feature_array[tfidf_sorting.argsort()[-top_n:]]
    # Return underrepresented topics (terms not in top_terms)
    return list(set(feature_array) - set(top_terms))

# Main orchestration function
def main():
    while True:
        try:
            existing_articles = load_existing_articles()
            if not isinstance(existing_articles, dict):
                print(f"Error: existing_articles is not a dictionary. Resetting to empty dictionary.")
                existing_articles = {}
            existing_titles = list(existing_articles.keys())
            
            underrepresented_topics = analyze_existing_topics(existing_articles)
            
            print(f"Generating new topics based on {len(existing_titles)} existing articles and {len(underrepresented_topics)} underrepresented topics.")
            topics = topic_generator_agent(existing_titles, underrepresented_topics)
            
            filepaths = []
            for topic in topics:
                try:
                    if len(topic) > 100:
                        print(f"Skipping overly long topic: {topic[:100]}...")
                        continue
                    print(f"Processing topic: {topic}")
                    
                    article = writer_agent(topic)
                    print(f"Article generated for topic: {topic}")
                    
                    optimized_article = seo_agent(article)
                    print(f"Article optimized for SEO: {topic}")
                    
                    if content_moderation_agent(topic, optimized_article, existing_articles):
                        filepath = front_end_agent(optimized_article, title=topic)
                        filepaths.append(filepath)
                        update_existing_articles(existing_articles, topic, optimized_article)
                        print(f"Article '{topic}' added to index and saved to {filepath}")
                    else:
                        print(f"Article '{topic}' was skipped due to duplication.")
                except Exception as e:
                    print(f"Error processing topic '{topic}': {e}")
                
                time.sleep(2)
            
            if filepaths:
                deployment_agent(filepaths)
            else:
                print("No new articles to deploy.")
            
            print("Sleeping for 10 minutes before generating new topics...")
            time.sleep(600)
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(60)

# Run the main function
if __name__ == "__main__":
    main()


