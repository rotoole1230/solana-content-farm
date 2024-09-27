import os
import time
import git
from groq import Groq
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Initialize the Groq client with your API key
client = Groq(
    api_key=('GROQ_API_KEY'),
)

# Paths to directories and files
CONTENT_DIR = 'content-farm-agent/site/content/articles'
INDEX_FILE = 'articles_index.json'
ANALYTICS_FILE = 'site_analytics.json'  # Placeholder for analytics data

# Initialize Git repository
repo = git.Repo('solana-content-farm')

# Agent 1: Topic Generator Agent
def topic_generator_agent(existing_topics, underrepresented_topics):
    prompt = (
        "Generate a list of 10 unique, in-depth article topics that explore detailed and technical aspects of the Solana blockchain. "
        f"Avoid topics that have already been covered: {existing_topics}. "
        f"Focus on these underrepresented areas: {underrepresented_topics}. "
        "Suggest areas that can be expounded upon differently."
    )
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-90b-text-preview",
    )
    topics = response.choices[0].message.content
    # Process topics into a list
    topics_list = [topic.strip("- ").strip() for topic in topics.split('\n') if topic.strip()]
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
    filename = title.lower().replace(' ', '-').replace('/', '-').replace(':', '').replace('"', '') + '.md'
    filepath = os.path.join(CONTENT_DIR, filename)
    
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
    # Add new files to Git
    repo.git.add(A=True)
    # Commit changes
    repo.index.commit("Add new articles")
    # Push to remote repository
    origin = repo.remote(name='origin')
    origin.push()
    print("Changes have been pushed to the repository.")

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
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            existing_articles = json.load(f)
    else:
        existing_articles = {}
    return existing_articles

# Helper function to update articles metadata
def update_existing_articles(existing_articles, title, article_content):
    existing_articles[title] = article_content
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_articles, f)

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
    # Endless loop to create an endless funnel of content
    while True:
        # Load existing articles
        existing_articles = load_existing_articles()
        existing_titles = list(existing_articles.keys())
        
        # Content Moderation Agent analyzes existing topics
        underrepresented_topics = analyze_existing_topics(existing_articles)
        
        # Generate new topics with guidance from Content Moderation Agent
        topics = topic_generator_agent(existing_titles, underrepresented_topics)
        filepaths = []
        for topic in topics:
            print(f"Processing topic: {topic}\n")
            article = writer_agent(topic)
            optimized_article = seo_agent(article)
            
            # Content Moderation Agent checks for duplication
            if content_moderation_agent(topic, optimized_article, existing_articles):
                filepath = front_end_agent(optimized_article, title=topic)
                filepaths.append(filepath)
                # Update existing articles metadata
                update_existing_articles(existing_articles, topic, optimized_article)
            else:
                print(f"Article '{topic}' was skipped due to duplication.")
            
            # Optional: Add a delay between processing each topic
            time.sleep(2)
        
        if filepaths:
            # Deploy the new articles
            deployment_agent(filepaths)
            
            # Load site analytics data (Placeholder)
            if os.path.exists(ANALYTICS_FILE):
                with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                    analytics_data = json.load(f)
            else:
                analytics_data = {}
            
            # Marketing Agent (Currently Inactive)
            # marketing_agent(budget=1000, analytics_data=analytics_data)
        
        # Optional: Sleep before generating new topics
        time.sleep(600)  # Sleep for 10 minutes before generating new topics

# Run the main function
if __name__ == "__main__":
    main()


